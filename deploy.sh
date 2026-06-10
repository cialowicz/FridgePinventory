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
 
# Check and enable SPI interface
echo "Checking SPI interface..."
# Raspberry Pi OS Bookworm moved the boot config to /boot/firmware.
if [ -f /boot/firmware/config.txt ]; then
    BOOT_CONFIG="/boot/firmware/config.txt"
else
    BOOT_CONFIG="/boot/config.txt"
fi
if ! ls /dev/spidev0.* &> /dev/null; then
    echo "WARNING: SPI devices not found. SPI interface may not be enabled."
    echo "Checking $BOOT_CONFIG..."

    if grep -q "^dtparam=spi=on" "$BOOT_CONFIG"; then
        echo "SPI is enabled in config but devices not found. You may need to reboot."
    elif grep -q "^#dtparam=spi=on" "$BOOT_CONFIG"; then
        echo "Enabling SPI in $BOOT_CONFIG..."
        sudo sed -i 's/^#dtparam=spi=on/dtparam=spi=on/' "$BOOT_CONFIG"
        echo "SPI enabled. REBOOT REQUIRED after this script completes!"
    elif grep -q "dtparam=spi=off" "$BOOT_CONFIG"; then
        echo "Enabling SPI in $BOOT_CONFIG..."
        sudo sed -i 's/dtparam=spi=off/dtparam=spi=on/' "$BOOT_CONFIG"
        echo "SPI enabled. REBOOT REQUIRED after this script completes!"
    else
        echo "Adding SPI enable to $BOOT_CONFIG..."
        echo "dtparam=spi=on" | sudo tee -a "$BOOT_CONFIG"
        echo "SPI enabled. REBOOT REQUIRED after this script completes!"
    fi
else
    echo "SPI interface is enabled and working."
fi

# The display driver relies on hardware chip-select (CE0 on GPIO 8); the
# spi0-0cs overlay disables all CS lines, so the panel ignores every SPI
# transfer while /dev/spidev0.0 still appears to work.
if grep -q "^dtoverlay=spi0-0cs" "$BOOT_CONFIG"; then
    echo "Disabling dtoverlay=spi0-0cs in $BOOT_CONFIG (breaks display CS)..."
    sudo sed -i 's/^dtoverlay=spi0-0cs/#dtoverlay=spi0-0cs/' "$BOOT_CONFIG"
    echo "spi0-0cs overlay disabled. REBOOT REQUIRED after this script completes!"
fi

# Route ALSA's default output to the USB speaker. The Pi 5 has no headphone
# jack, and without this the chimes/TTS go to a nonexistent default device.
# The card is referenced by NAME because card numbers shift across boots
# when multiple USB audio devices (mic + speaker) are attached.
AUDIO_OUTPUT_CARD="UACDemoV10"
echo "Configuring ALSA default output..."
if aplay -l 2>/dev/null | grep -q "$AUDIO_OUTPUT_CARD"; then
    if [ -f /etc/asound.conf ] && ! grep -q "Managed by FridgePinventory" /etc/asound.conf; then
        BACKUP="/etc/asound.conf.bak.$(date +%Y%m%d%H%M%S)"
        echo "Backing up existing /etc/asound.conf to $BACKUP"
        sudo cp /etc/asound.conf "$BACKUP"
    fi
    sudo tee /etc/asound.conf > /dev/null <<EOF
# Managed by FridgePinventory deploy.sh — route default audio to the USB speaker
# The ! override is required: alsa.conf defines these nodes as integers, and
# assigning a string card name without ! is a type conflict that makes ALSA
# discard the entire configuration (no audio devices at all).
defaults.pcm.!card "$AUDIO_OUTPUT_CARD"
defaults.ctl.!card "$AUDIO_OUTPUT_CARD"
EOF
    echo "ALSA default output set to card '$AUDIO_OUTPUT_CARD'."
    # USB speakers commonly ship with the mixer muted or at 0%; raise
    # whichever playback control this card exposes (best effort).
    for control in PCM Speaker Master Headphone; do
        if amixer -c "$AUDIO_OUTPUT_CARD" sset "$control" 85% unmute > /dev/null 2>&1; then
            echo "Set '$control' on $AUDIO_OUTPUT_CARD to 85%, unmuted."
        fi
    done
    sudo alsactl store 2>/dev/null || true
else
    echo "WARNING: audio output card '$AUDIO_OUTPUT_CARD' not detected;"
    echo "         leaving /etc/asound.conf untouched. Plug in the USB"
    echo "         speaker and re-run deploy.sh to configure audio output."
fi

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
    python3-spidev \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-alsa
 
# Verify espeak-ng installation
echo "Verifying espeak-ng installation..."
if ! command -v espeak-ng &> /dev/null; then
    echo "Error: espeak-ng not found in PATH"
    echo "Checking installation location..."
    find /usr -name "espeak-ng" 2>/dev/null || echo "espeak-ng not found in /usr"
    exit 1
fi
echo "espeak-ng found at: $(which espeak-ng)"
 
# Create and activate a virtual environment for e-Paper
echo "DEBUG: Current user for venv: $(whoami)"
echo "DEBUG: Target venv path: ~/.epaper_venv which is $(eval echo ~/.epaper_venv)"
echo "Setting up virtual environment for e-Paper..."
python3 -m venv ~/.epaper_venv
 
echo "DEBUG: Checking if venv was created..."
if [ -f "$(eval echo ~/.epaper_venv)/bin/activate" ]; then
    echo "DEBUG: Venv activate script FOUND."
else
    echo "DEBUG: Venv activate script NOT FOUND. Venv creation likely FAILED. Exiting."
    exit 1
fi
 
source ~/.epaper_venv/bin/activate
echo "DEBUG: Venv activated. 'which python' should point to venv: $(which python)"
echo "DEBUG: 'pip --version' in venv: $(pip --version)"
 
# Install Waveshare e-Paper library and other Python dependencies
echo "Installing Python dependencies into venv..."
 
echo "DEBUG: Installing Waveshare e-Paper library..."
# Save current directory
ORIG_DIR=$(pwd)
cd /tmp
rm -rf e-Paper

# Clone Waveshare repository
echo "Cloning Waveshare e-Paper repository..."
if ! git clone https://github.com/waveshareteam/e-Paper.git; then
    echo "ERROR: Failed to clone Waveshare repository"
    cd $ORIG_DIR
    exit 1
fi

cd e-Paper/RaspberryPi_JetsonNano/python

# Install requirements first
if [ -f requirements.txt ]; then
    echo "Installing Waveshare requirements..."
    pip install -r requirements.txt
fi

# Install the library
echo "Installing Waveshare library..."
# Use pip to install the library from the local setup.py with verbose output
if ! pip install -v .; then
    echo "ERROR: Failed to install Waveshare library"
    cd $ORIG_DIR
    exit 1
fi

# Check what was actually installed
echo "DEBUG: Checking installed package contents..."
pip show waveshare-epd || echo "waveshare-epd package not found"
python -c "import site; print('Site packages:', site.getsitepackages())" 2>/dev/null || true

# Install epd3in97 driver from our repo
echo "DEBUG: Installing epd3in97 driver from repository..."
if ! python -c "import epd3in97" 2>/dev/null; then
    echo "Installing epd3in97 driver from repo..."
    
    # Get the site-packages location
    SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])" 2>/dev/null)
    if [ -n "$SITE_PACKAGES" ] && [ -d "$SITE_PACKAGES/waveshare_epd" ]; then
        # Copy driver files from our project repo (not from /tmp/e-Paper)
        REPO_DRIVERS="$ORIG_DIR/waveshare_drivers"
        if [ -f "$REPO_DRIVERS/epd3in97.py" ] && [ -f "$REPO_DRIVERS/epdconfig.py" ]; then
            echo "Installing drivers from: $REPO_DRIVERS"
            echo "  -> $SITE_PACKAGES/waveshare_epd/ (for waveshare_epd.epd3in97 import)"
            cp "$REPO_DRIVERS/epd3in97.py" "$SITE_PACKAGES/waveshare_epd/"
            cp "$REPO_DRIVERS/epdconfig.py" "$SITE_PACKAGES/waveshare_epd/"
            
            echo "✓ epd3in97 driver installed successfully from repository"
        else
            echo "❌ ERROR: Driver files not found in repository at $REPO_DRIVERS"
            echo "   Expected files:"
            echo "     - $REPO_DRIVERS/epd3in97.py"
            echo "     - $REPO_DRIVERS/epdconfig.py"
            exit 1
        fi
    else
        echo "❌ ERROR: Could not find waveshare_epd package directory at $SITE_PACKAGES"
        exit 1
    fi
else
    echo "✓ epd3in97 driver already available"
fi

cd $ORIG_DIR
echo "DEBUG: Waveshare install command finished."

# Verify installation by trying to import
echo "Verifying Waveshare library installation..."
if python -c "from waveshare_epd import epd3in97; print('✓ waveshare_epd.epd3in97 import successful')" 2>/dev/null; then
    echo "✓ Waveshare library installed successfully (3.97 driver found)"
elif python -c "import epd3in97; print('✓ epd3in97 direct import successful')" 2>/dev/null; then
    echo "✓ Waveshare library installed successfully (3.97 driver direct import)"
else
    echo "WARNING: Waveshare library may not have installed correctly"
    echo "Library will fall back to mock display if hardware import fails"
    echo "DEBUG: Testing various import methods..."
    python -c "import sys; print('Python path:', sys.path)" 2>/dev/null || true
    python -c "try: import waveshare_epd; print('waveshare_epd module found'); print('Available modules:', [x for x in dir(waveshare_epd) if 'epd' in x]); except Exception as e: print('waveshare_epd not found:', e)" 2>/dev/null || true
    echo "DEBUG: Testing our actual display module import..."
    python -c "
import sys
import os
sys.path.insert(0, '$(pwd)/src')
try:
    import pi_inventory_system.waveshare_display as waveshare_display
    waveshare_display.ensure_waveshare_lib()
    print(f'✓ Our waveshare_display module imports successfully')
    print(f'✓ WAVESHARE_AVAILABLE = {waveshare_display.WAVESHARE_AVAILABLE}')
    if waveshare_display.WAVESHARE_AVAILABLE:
        print('✓ Waveshare library is available and should work on Pi')
    else:
        print('⚠ Waveshare library not available, will use mock display')
except Exception as e:
    print(f'✗ Error importing our waveshare_display module: {e}')
    import traceback
    traceback.print_exc()
" 2>/dev/null || echo "Module import test failed"
fi
 
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

echo "DEBUG: Attempting to install RPi.GPIO..."
pip install RPi.GPIO
echo "DEBUG: RPi.GPIO install command finished. Checking..."
pip list | grep -i RPi.GPIO || echo "DEBUG: RPi.GPIO NOT found."

echo "DEBUG: Attempting to install spidev..."
pip install spidev
echo "DEBUG: spidev install command finished. Checking..."
pip list | grep -i spidev || echo "DEBUG: spidev NOT found."

echo "DEBUG: Attempting to install Pillow..."
pip install Pillow
echo "DEBUG: Pillow install command finished. Checking..."
pip list | grep -i Pillow || echo "DEBUG: Pillow NOT found."

echo "DEBUG: Attempting to install gpiozero..."
pip install gpiozero
echo "DEBUG: gpiozero install command finished. Checking..."
pip list | grep -i gpiozero || echo "DEBUG: gpiozero NOT found."

echo "DEBUG: Attempting to install lgpio..."
pip install lgpio
echo "DEBUG: lgpio install command finished. Checking..."
pip list | grep -i lgpio || echo "DEBUG: lgpio NOT found."

# Install the current project in editable mode into the venv
echo "Installing FridgePinventory into virtual environment..."
pip install -e .

# Final comprehensive test of the entire system
echo "DEBUG: Final system integration test..."
python -c "
import sys
import os
try:
    # Test main application can import display manager
    from pi_inventory_system.display_manager import initialize_display
    print('✓ Display manager imports successfully')
    
    # Test waveshare display module
    import pi_inventory_system.waveshare_display as waveshare_display
    print('✓ Waveshare display module imports successfully')
    waveshare_display.ensure_waveshare_lib()
    print(f'✓ WAVESHARE_AVAILABLE = {waveshare_display.WAVESHARE_AVAILABLE}')
    
    # Try creating a display instance (should work even on non-Pi with mock)
    display = waveshare_display.WaveshareDisplay()
    print('✓ WaveshareDisplay instance created successfully')
    
    if waveshare_display.WAVESHARE_AVAILABLE:
        print('🎉 SUCCESS: Waveshare library is properly installed and ready for Pi deployment!')
    else:
        print('⚠️  INFO: Mock display will be used (expected when not on Pi)')
        
except Exception as e:
    print(f'❌ FAILED: System integration test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"
 
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
Environment="VIRTUAL_ENV=${SERVICE_USER_EFFECTIVE_HOME}/.epaper_venv"
Environment="PATH=${SERVICE_USER_EFFECTIVE_HOME}/.epaper_venv/bin:$PATH"
Environment="ESPEAK_DATA_PATH=/usr/share/espeak-ng-data"
ExecStart=${SERVICE_USER_EFFECTIVE_HOME}/.epaper_venv/bin/python -m pi_inventory_system.main
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

# Check if reboot is needed
if ! ls /dev/spidev0.* &> /dev/null; then
    echo ""
    echo "⚠️  IMPORTANT: REBOOT REQUIRED ⚠️"
    echo "SPI interface was enabled but requires a reboot to take effect."
    echo "After rebooting:"
    echo "  1. Run 'fridge-diagnostic' (in ~/.epaper_venv) to verify hardware"
    echo "  2. Start the service: sudo systemctl start fridgepinventory.service"
    echo ""
else
    echo "To start the service now, run: sudo systemctl start fridgepinventory.service"
fi

echo "To check the status, run: sudo systemctl status fridgepinventory.service"
echo "To view logs, run: journalctl -u fridgepinventory.service -f"
