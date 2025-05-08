#!/bin/bash

# Exit on error
set -e

echo "Setting up FridgePinventory on Raspberry Pi..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv /home/admin/fridgepinventory_venv
source /home/admin/fridgepinventory_venv/bin/activate

# Install system dependencies (like PortAudio)
echo "Installing system dependencies..."
sudo apt-get update && sudo apt-get install -y portaudio19-dev espeak-ng

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -e .

# Create systemd service file
echo "Creating systemd service..."
sudo tee /etc/systemd/system/fridgepinventory.service > /dev/null << EOL
[Unit]
Description=FridgePinventory Service
After=network.target

[Service]
Type=simple
User=admin
WorkingDirectory=/home/admin/FridgePinventory
Environment="PYTHONPATH=/home/admin/FridgePinventory/src"
ExecStart=/home/admin/fridgepinventory_venv/bin/python -m pi_inventory_system.main
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