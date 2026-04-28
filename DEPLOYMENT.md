# FridgePinventory Deployment Guide

This guide will help you set up FridgePinventory on your Raspberry Pi.

## Prerequisites

- Raspberry Pi (tested on Raspberry Pi 5)
- Raspberry Pi OS (tested on Raspberry Pi OS Bookworm)
- Internet connection
- Required hardware:
  - Waveshare 3.97" e-Paper HAT+ display
  - HC-SR501 PIR Infrared Motion Sensor
  - USB microphone
  - USB speaker

## Hardware Setup

1. Connect the Waveshare e-Paper HAT+ to the Raspberry Pi GPIO header
2. Connect the motion sensor to the GPIO pins: 05 (5v), 06 (gnd), 07 (GPIO04/GPIO_GCLK)
3. Connect the USB microphone
4. Connect the USB speaker

## Software Setup

1. Enable SPI Interface on Raspberry Pi:
   ```bash
   sudo raspi-config
   ```
   Select "Interface Options" -> "SPI" -> "Yes", then reboot

2. Install system-level dependencies (required for building Python packages):
   ```bash
   # Required for building RPi.GPIO and PyAudio
   sudo apt install -y python3-dev portaudio19-dev espeak-ng
   ```

3. Clone the repository:
   ```bash
   cd ~
   git clone https://github.com/cialowicz/FridgePinventory.git
   cd FridgePinventory
   ```

4. Make the deployment script executable:
   ```bash
   chmod +x deploy.sh
   ```

5. Run the deployment script:
   ```bash
   ./deploy.sh
   ```
   This script creates the e-paper virtual environment, installs Python dependencies,
   installs the Waveshare display library, and downloads the spaCy model used by the
   command processor when NLP parsing is enabled.

6. Start the service:
   ```bash
   sudo systemctl start fridgepinventory.service
   ```

## Verifying the Installation

1. Check the service status:
   ```bash
   sudo systemctl status fridgepinventory.service
   ```

2. View the logs:
   ```bash
   journalctl -u fridgepinventory.service -f
   ```

## Troubleshooting

### Service won't start
- Check the logs: `journalctl -u fridgepinventory.service -f`
- Verify hardware connections
- Check file permissions
- Ensure all dependencies are installed:
  - System packages: `python3-dev portaudio19-dev espeak-ng`
  - Python packages: Check `pyproject.toml`

### Display issues
- Verify GPIO connections
- Check display driver installation
- Ensure correct display model is configured

### Audio issues
- Check audio device configuration:
  ```bash
  # List audio devices
  arecord -l
  aplay -l
  
  # Test audio output
  aplay /usr/share/sounds/alsa/Front_Center.wav
  
  # Test microphone
  arecord -d 5 test.wav
  aplay test.wav
  ```
- Verify USB microphone and speaker connections
- Check if devices are recognized: `lsusb`

### Motion sensor issues
- Verify GPIO connections
- Check sensor configuration
- Test sensor manually

## Updating the Software

1. Pull the latest changes:
   ```bash
   cd ~/FridgePinventory
   git pull
   ```

2. Re-run the deployment script:
   ```bash
   ./deploy.sh
   ```

3. Restart the service:
   ```bash
   sudo systemctl restart fridgepinventory.service
   ```

## Uninstalling

1. Stop the service:
   ```bash
   sudo systemctl stop fridgepinventory.service
   sudo systemctl disable fridgepinventory.service
   ```

2. Remove the service file:
   ```bash
   sudo rm /etc/systemd/system/fridgepinventory.service
   ```

3. Uninstall the package:
   ```bash
   pipx uninstall FridgePinventory
   ```

4. Remove the project directory:
   ```bash
   rm -rf ~/FridgePinventory
   ``` 
