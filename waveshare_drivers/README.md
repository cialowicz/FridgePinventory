# Waveshare E-Paper Drivers

This directory contains the official Waveshare drivers for the 3.97" e-Paper HAT+ display.

## Files

- `epd3in97.py` - Python driver for 3.97" e-Paper display (800x480, 4-level grayscale)
- `epdconfig.py` - Configuration and GPIO interface for Waveshare displays

## Source

These files are from the official Waveshare 3.97" e-Paper demo package:
- **Source**: Waveshare official demo
- **Display**: 3.97" e-Paper HAT+ (800×480 pixels, 4-level grayscale)
- **Version**: Compatible with Raspberry Pi via SPI interface

## Installation

These drivers are automatically installed by the `deploy.sh` script to the waveshare_epd package directory.

## Usage

```python
from waveshare_epd import epd3in97

epd = epd3in97.EPD()
epd.init()
epd.Clear()
# Display operations...
epd.sleep()
```

## Display Specifications

- **Resolution**: 800×480 pixels
- **Colors**: 4-level grayscale (White, Light Gray, Dark Gray, Black)
- **Interface**: SPI
- **Refresh Time**: ~3.5 seconds (full), ~0.6 seconds (partial)
- **Viewing Angle**: Nearly 180°
- **Power**: Ultra-low power consumption
