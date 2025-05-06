# FridgePinventory Deployment Guide

This guide will help you set up FridgePinventory on your Raspberry Pi.

## Prerequisites

- Raspberry Pi (tested on Raspberry Pi 4)
- Raspberry Pi OS (tested on Raspberry Pi OS Bullseye)
- Internet connection
- Required hardware:
  - eInk display
  - Motion sensor
  - Microphone
  - Speaker

## Hardware Setup

1. Connect the eInk display to the Raspberry Pi's GPIO pins
2. Connect the motion sensor to the GPIO pins: 05 (5v), 06 (gnd), 07 (GPIO04/GPIO_GCLK)
3. Connect the USB microphone
4. Connect the USB speaker

## Software Setup

1. Clone the repository:
   ```bash
   cd /home/pi
   git clone https://github.com/cialowicz/FridgePinventory.git
   cd FridgePinventory
   ```

2. Make the deployment script executable:
   ```bash
   chmod +x deploy.sh
   ```

3. Run the deployment script:
   ```bash
   ./deploy.sh
   ```

4. Start the service:
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
- Ensure all dependencies are installed (check pyproject.toml)

### Display issues
- Verify GPIO connections
- Check display driver installation
- Ensure correct display model is configured

### Audio issues
- Check audio device configuration
- Verify microphone and speaker connections
- Test audio output: `aplay /usr/share/sounds/alsa/Front_Center.wav`

### Motion sensor issues
- Verify GPIO connections
- Check sensor configuration
- Test sensor manually

## Updating the Software

1. Pull the latest changes:
   ```bash
   cd /home/pi/FridgePinventory
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

3. Remove the virtual environment:
   ```bash
   rm -rf /home/pi/fridgepinventory_venv
   ```

4. Remove the project directory:
   ```bash
   rm -rf /home/pi/FridgePinventory
   ``` 