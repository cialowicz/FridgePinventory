#!/bin/bash

# Exit on error
set -e

echo "Setting up FridgePinventory..."

# Check if we're in the project directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: Please run this script from the FridgePinventory project directory"
    exit 1
fi

# Remove existing service if it exists
echo "Removing existing service..."
if systemctl is-active --quiet fridgepinventory.service; then
    sudo systemctl stop fridgepinventory.service
fi
if systemctl is-enabled --quiet fridgepinventory.service; then
    sudo systemctl disable fridgepinventory.service
fi
sudo rm -f /etc/systemd/system/fridgepinventory.service
sudo systemctl daemon-reload

# Install system dependencies required for building packages
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y \
    python3-dev \
    portaudio19-dev \
    espeak-ng \
    libasound2-dev \
    python3-pyaudio \
    python3-pip \
    python3-venv \
    git \
    libopenjp2-7 \
    libtiff6 \
    fonts-dejavu \
    raspi-gpio \
    python3-pil \
    python3-pil.imagetk

# Verify espeak-ng installation
echo "Verifying espeak-ng installation..."
if ! command -v espeak-ng &> /dev/null; then
    echo "Error: espeak-ng not found in PATH"
    echo "Checking installation location..."
    find /usr -name "espeak-ng" 2>/dev/null || echo "espeak-ng not found in /usr"
    exit 1
fi
echo "espeak-ng found at: $(which espeak-ng)"

# Create and activate a virtual environment for Inky
echo "Setting up virtual environment for Inky..."
python3 -m venv ~/.inky_venv
source ~/.inky_venv/bin/activate

# Install Inky and other Python dependencies
echo "Installing Python dependencies..."
pip install git+https://github.com/pimoroni/inky.git
pip install SpeechRecognition
pip install pyaudio
pip install spacy
pip install word2number

# Deactivate the virtual environment
deactivate

# Install pipx if not already installed
if ! command -v pipx &> /dev/null; then
    echo "Installing pipx..."
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath
    # Need to reload shell environment to get pipx in PATH
    . ~/.profile
fi

# Install the package using pipx
echo "Installing FridgePinventory..."
pipx install --include-deps -e .

# Create systemd service file
echo "Creating systemd service..."

# Determine home directory for the service user
# $USER here is the user running this deploy.sh script
SERVICE_USER_EFFECTIVE_HOME=$(eval echo "~$USER")

sudo tee /etc/systemd/system/fridgepinventory.service > /dev/null << EOL
[Unit]
Description=FridgePinventory Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment="PYTHONPATH=$(pwd)/src"
Environment="JACK_NO_AUDIO_RESERVATION=1"
Environment="JACK_NO_START_SERVER=1"
Environment="VIRTUAL_ENV=${SERVICE_USER_EFFECTIVE_HOME}/.inky_venv"
Environment="PATH=${SERVICE_USER_EFFECTIVE_HOME}/.inky_venv/bin:$PATH"
Environment="ESPEAK_DATA_PATH=/usr/share/espeak-ng-data"
ExecStart=${SERVICE_USER_EFFECTIVE_HOME}/.inky_venv/bin/python -m pi_inventory_system.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd and enable service
echo "Enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable fridgepinventory.service

echo "Setup complete! The service will start automatically on boot."
echo "To start the service now, run: sudo systemctl start fridgepinventory.service"
echo "To check the status, run: sudo systemctl status fridgepinventory.service"
echo "To view logs, run: journalctl -u fridgepinventory.service -f" 