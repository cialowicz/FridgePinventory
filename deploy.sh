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
    swig \
    libpulse-dev \
    flac \
    libjack-jackd2-dev \
    python3-pip \
    python3-venv \
    git \
    libopenjp2-7 \
    libtiff6 \
    fonts-dejavu \
    raspi-gpio \
    python3-spidev
 
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
echo "DEBUG: Current user for venv: $(whoami)"
echo "DEBUG: Target venv path: ~/.inky_venv which is $(eval echo ~/.inky_venv)"
echo "Setting up virtual environment for Inky..."
python3 -m venv ~/.inky_venv
 
echo "DEBUG: Checking if venv was created..."
if [ -f "$(eval echo ~/.inky_venv)/bin/activate" ]; then
    echo "DEBUG: Venv activate script FOUND."
else
    echo "DEBUG: Venv activate script NOT FOUND. Venv creation likely FAILED. Exiting."
    exit 1
fi
 
source ~/.inky_venv/bin/activate
echo "DEBUG: Venv activated. 'which python' should point to venv: $(which python)"
echo "DEBUG: 'pip --version' in venv: $(pip --version)"
 
# Install Inky and other Python dependencies
echo "Installing Python dependencies into venv..."
 
echo "DEBUG: Attempting to install Inky..."
pip install git+https://github.com/pimoroni/inky.git
echo "DEBUG: Inky install command finished. Checking if inky is in pip list..."
pip list | grep -i inky || echo "DEBUG: Inky NOT found in pip list after install attempt."
 
echo "DEBUG: Attempting to install SpeechRecognition..."
pip install SpeechRecognition
echo "DEBUG: SpeechRecognition install command finished. Checking..."
pip list | grep -i SpeechRecognition || echo "DEBUG: SpeechRecognition NOT found."
 
echo "DEBUG: Attempting to install pyaudio..."
pip install pyaudio
echo "DEBUG: pyaudio install command finished. Checking..."
pip list | grep -i pyaudio || echo "DEBUG: pyaudio NOT found."
 
echo "DEBUG: Attempting to install spacy..."
pip install spacy
echo "DEBUG: spacy install command finished. Checking..."
pip list | grep -i spacy || echo "DEBUG: spacy NOT found."
 
echo "DEBUG: Downloading spacy model en_core_web_sm..."
python -m spacy download en_core_web_sm
echo "DEBUG: Spacy model download command finished."
 
echo "DEBUG: Attempting to install word2number..."
pip install word2number
echo "DEBUG: word2number install command finished. Checking..."
pip list | grep -i word2number || echo "DEBUG: word2number NOT found."
 
echo "DEBUG: Attempting to install pyttsx3..."
pip install pyttsx3
echo "DEBUG: pyttsx3 install command finished. Checking..."
pip list | grep -i pyttsx3 || echo "DEBUG: pyttsx3 NOT found."
 
echo "DEBUG: Attempting to install numpy..."
pip install numpy
echo "DEBUG: numpy install command finished. Checking..."
pip list | grep -i numpy || echo "DEBUG: numpy NOT found."

echo "DEBUG: Attempting to install PyYAML..."
pip install PyYAML
echo "DEBUG: PyYAML install command finished. Checking..."
pip list | grep -i PyYAML || echo "DEBUG: PyYAML NOT found."

echo "DEBUG: Attempting to install playsound..."
pip install playsound
echo "DEBUG: playsound install command finished. Checking..."
pip list | grep -i playsound || echo "DEBUG: playsound NOT found."

echo "DEBUG: Attempting to install pocketsphinx..."
pip install pocketsphinx
echo "DEBUG: pocketsphinx install command finished. Checking..."
pip list | grep -i pocketsphinx || echo "DEBUG: pocketsphinx NOT found."
 
# Install the current project in editable mode into the venv
echo "Installing FridgePinventory into virtual environment..."
pip install -e .
 
# Deactivate the virtual environment
deactivate
 
# Add user to necessary groups for hardware access
echo "Adding user $USER to audio, gpio, spi groups..."
sudo usermod -a -G audio "$USER"
sudo usermod -a -G gpio "$USER"
sudo usermod -a -G spi "$USER"
echo "NOTE: You may need to reboot for group changes to take full effect."
 
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
