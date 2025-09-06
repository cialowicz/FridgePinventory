# full_hardware_diagnostic.py

###
### Run with:
### source ~/.epaper_venv/bin/activate && python3 full_hardware_diagnostic.py
###

import time
import os
import sys
import subprocess

# --- Test Configuration ---
MOTION_SENSOR_PIN = 4
MIC_TEST_DURATION = 3  # seconds
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480
# ------------------------

# --- Helper Functions ---
def print_header(title):
    print(f"\n{'='*10} {title.upper()} {'='*10}")

def print_status(message, status):
    status_str = "OK" if status else "FAIL"
    print(f"- {message}: [{status_str}]")
    return status

def update_display(display, draw, image, font, lines):
    if display:
        # Clear the image (white background for Waveshare)
        draw.rectangle((0, 0, display.WIDTH, display.HEIGHT), fill=255)
        y = 5
        for line in lines:
            draw.text((5, y), line, font=font, fill=0)  # Black text
            bbox = font.getbbox('A')
            y += bbox[3] - bbox[1] + 2  # Height of font + 2px padding
        display.display_image(image)

# --- Test Functions ---

def test_spi_interface(lines):
    print_header("SPI Interface Check")
    try:
        # Check if SPI devices exist
        spi_devices = ['/dev/spidev0.0', '/dev/spidev0.1']
        spi_exists = any(os.path.exists(device) for device in spi_devices)
        
        for device in spi_devices:
            exists = os.path.exists(device)
            print(f"SPI device {device}: {'EXISTS' if exists else 'MISSING'}")
        
        # Check if SPI is enabled in config
        try:
            with open('/boot/config.txt', 'r') as f:
                config_content = f.read()
                spi_line = None
                for line in config_content.split('\n'):
                    if 'dtparam=spi=on' in line:
                        spi_line = line.strip()
                        break
                
                if spi_line and not spi_line.startswith('#'):
                    print("SPI enabled in /boot/config.txt: YES")
                    config_enabled = True
                else:
                    print("SPI enabled in /boot/config.txt: NO")
                    config_enabled = False
        except Exception as e:
            print(f"Could not check /boot/config.txt: {e}")
            config_enabled = False
        
        # Check lsmod for SPI modules
        try:
            result = subprocess.run(['lsmod'], capture_output=True, text=True)
            spi_modules = [line for line in result.stdout.split('\n') if 'spi' in line.lower()]
            modules_loaded = len(spi_modules) > 0
            print(f"SPI kernel modules loaded: {'YES' if modules_loaded else 'NO'}")
            if spi_modules:
                for module in spi_modules[:3]:  # Show first 3
                    print(f"  {module}")
        except Exception as e:
            print(f"Could not check kernel modules: {e}")
            modules_loaded = False
        
        # Overall SPI status
        spi_ok = spi_exists and config_enabled
        print_status("SPI interface ready", spi_ok)
        
        if spi_ok:
            lines.append("SPI: OK")
        else:
            lines.append("SPI: DISABLED")
            print("\n*** SPI ISSUE DETECTED ***")
            print("To enable SPI:")
            print("1. Run: sudo raspi-config")
            print("2. Go to: Interface Options -> SPI -> Enable")
            print("3. Reboot with: sudo reboot")
        
        return spi_ok
        
    except Exception as e:
        print_status(f"SPI check failed: {e}", False)
        lines.append("SPI: ERROR")
        return False

def test_waveshare_library(lines):
    print_header("Waveshare Library Check")
    try:
        # Check common library paths
        lib_paths = [
            '/home/admin/e-Paper/RaspberryPi_JetsonNano/python/lib',
            '/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib',
            '/opt/e-Paper/RaspberryPi_JetsonNano/python/lib',
        ]
        
        lib_found = False
        for lib_path in lib_paths:
            exists = os.path.exists(lib_path)
            print(f"Library path {lib_path}: {'EXISTS' if exists else 'MISSING'}")
            if exists:
                lib_found = True
                try:
                    epd_files = [f for f in os.listdir(lib_path) if f.startswith('epd3in97')]
                    print(f"  EPD3in97 files: {epd_files}")
                except:
                    pass
        
        # Try importing
        import_success = False
        import_methods = [
            "from waveshare_epd import epd3in97",
            "import epd3in97"
        ]
        
        for method in import_methods:
            try:
                # Add lib paths to sys.path for testing
                for lib_path in lib_paths:
                    if os.path.exists(lib_path) and lib_path not in sys.path:
                        sys.path.insert(0, lib_path)
                
                exec(method)
                print(f"Import SUCCESS: {method}")
                import_success = True
                break
            except ImportError as e:
                print(f"Import FAILED: {method} - {str(e)[:60]}...")
        
        # Overall status
        library_ok = lib_found and import_success
        print_status("Waveshare library available", library_ok)
        
        if library_ok:
            lines.append("Waveshare Lib: OK")
        else:
            lines.append("Waveshare Lib: MISSING")
            print("\n*** WAVESHARE LIBRARY ISSUE ***")
            print("The Waveshare e-Paper library may need to be installed.")
        
        return library_ok
        
    except Exception as e:
        print_status(f"Library check failed: {e}", False)
        lines.append("Waveshare Lib: ERROR")
        return False

def test_display(lines, font):
    print_header("Display Test")
    try:
        # Import the Waveshare display module
        import sys
        import os
        # Add the project source to path
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        src_path = os.path.join(project_root, 'src')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        from pi_inventory_system.waveshare_display import WaveshareDisplay
        from PIL import Image, ImageDraw
        
        print("Initializing Waveshare 3.97\" e-Paper display...")
        display = WaveshareDisplay()
        if display.initialize():
            # Create grayscale image for Waveshare
            image = Image.new("L", (display.WIDTH, display.HEIGHT), 255)  # White background
            draw = ImageDraw.Draw(image)
            print_status("Waveshare display initialized", True)
            lines.append("Display: OK")
            return display, draw, image
        else:
            print_status("Waveshare display initialization failed", False)
            lines.append("Display: FAIL")
            return None, None, None
    except Exception as e:
        print_status(f"Display initialization failed: {e}", False)
        lines.append("Display: FAIL")
        return None, None, None

def test_audio_devices(lines):
    print_header("Audio Device Listing")
    try:
        import pyaudio
        import os
        
        # Set environment variables to suppress ALSA errors
        os.environ['ALSA_ERROR_LEVEL'] = '0'
        os.environ['ALSA_LOG_LEVEL'] = '0'
        
        pa = pyaudio.PyAudio()
        
        print("\nInput Devices (Microphones):")
        mic_found = False
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get('maxInputChannels') > 0:
                mic_found = True
                print(f"  - Index {info['index']}: {info['name']}")
        if not mic_found:
            print("  No input devices found.")
        
        print("\nOutput Devices (Speakers):")
        speaker_found = False
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get('maxOutputChannels') > 0:
                speaker_found = True
                print(f"  - Index {info['index']}: {info['name']}")
        if not speaker_found:
            print("  No output devices found.")

        pa.terminate()
        
        print_status("Audio device scan complete", True)
        lines.append("Audio List: OK")
    except Exception as e:
        print_status(f"PyAudio failed: {e}", False)
        lines.append("Audio List: FAIL")

def test_speaker(lines):
    print_header("Speaker Test")
    try:
        from playsound import playsound
        sound_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'assets', 'sounds', 'success.wav')
        if not os.path.exists(sound_file):
            print_status(f"Sound file not found at {sound_file}", False)
            lines.append("Speaker: FAIL (file missing)")
            return

        print("Playing test sound...", end="", flush=True)
        playsound(sound_file)
        print(" Done.")
        print_status("Speaker test successful", True)
        lines.append("Speaker: OK")
    except Exception as e:
        print_status(f"Speaker test failed: {e}", False)
        lines.append("Speaker: FAIL")

def test_microphone(lines):
    print_header("Microphone Test")
    try:
        import pyaudio
        import os
        
        # Set environment variables to suppress ALSA errors  
        os.environ['ALSA_ERROR_LEVEL'] = '0'
        os.environ['ALSA_LOG_LEVEL'] = '0'
        
        pa = pyaudio.PyAudio()
        print(f"Recording for {MIC_TEST_DURATION} seconds... Speak now!")
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
        frames = []
        for _ in range(0, int(16000 / 1024 * MIC_TEST_DURATION)):
            data = stream.read(1024)
            frames.append(data)
        stream.stop_stream()
        stream.close()
        pa.terminate()
        
        print("Recording complete.")
        is_silent = all(b == 0 for b in b''.join(frames))
        if not is_silent:
            print_status("Microphone captured non-silent audio", True)
            lines.append("Mic: OK")
        else:
            print_status("Microphone captured only silence", False)
            lines.append("Mic: SILENT")
    except Exception as e:
        print_status(f"Microphone test failed: {e}", False)
        lines.append("Mic: FAIL")

def _is_raspberry_pi_5():
    try:
        with open('/proc/device-tree/model', 'r') as f:
            return 'raspberry pi 5' in f.read().lower()
    except FileNotFoundError:
        return False

def _read_pinctrl(pin: int) -> bool:
    try:
        result = subprocess.run(
            ['sudo', 'pinctrl', 'get', str(pin)], 
            capture_output=True, 
            text=True, 
            check=True,
            timeout=2
        )
        print(f"DEBUG: pinctrl stdout: {result.stdout.strip()}")
        return 'level=1' in result.stdout
    except subprocess.CalledProcessError as e:
        print(f"DEBUG: pinctrl command failed with exit code {e.returncode}.")
        print(f"DEBUG: pinctrl stderr: {e.stderr.strip()}")
        return False
    except Exception as e:
        print(f"DEBUG: An unexpected error occurred while running pinctrl: {e}")
        return False

def test_motion_sensor(lines):
    print_header("Motion Sensor Test")
    try:
        print("Please wave your hand in front of the sensor for 5 seconds...")
        motion_detected = False
        if _is_raspberry_pi_5():
            print("INFO: Using Pi 5 'pinctrl' method.")
            try:
                # On Pi 5, we must explicitly set the pin as an input with pull-down
                print(f"INFO: Configuring GPIO {MOTION_SENSOR_PIN} as input with pull-down.")
                subprocess.run(['sudo', 'pinctrl', 'set', str(MOTION_SENSOR_PIN), 'ip', 'pd'], check=True)
            except Exception as e:
                print(f"ERROR: Failed to configure GPIO pin: {e}")

            for _ in range(10):
                if _read_pinctrl(MOTION_SENSOR_PIN):
                    motion_detected = True
                    break
                time.sleep(0.5)
                print(".", end="", flush=True)
        else:
            print("DEBUG: Using RPi.GPIO method for older Pi.")
            import RPi.GPIO as GPIO
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(MOTION_SENSOR_PIN, GPIO.IN)
                for _ in range(10):
                    if GPIO.input(MOTION_SENSOR_PIN):
                        motion_detected = True
                        break
                    time.sleep(0.5)
                    print(".", end="", flush=True)
            finally:
                GPIO.cleanup()

        print()
        print_status("Motion sensor check", motion_detected)
        lines.append(f"Motion: {'OK' if motion_detected else 'FAIL'}")
    except Exception as e:
        print_status(f"Motion sensor test failed: {e}", False)
        lines.append("Motion: FAIL")

# --- Main Execution ---
if __name__ == "__main__":
    print("Attempting to stop 'fridgepinventory.service' to free up hardware...")
    subprocess.run(["sudo", "systemctl", "stop", "fridgepinventory.service"], check=False)
    time.sleep(1)

    try:
        from PIL import ImageFont
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except IOError:
        font = ImageFont.load_default()

    display_lines = ["Hardware Diagnostic:"]
    
    # Test SPI and Waveshare library first - these are prerequisites for display
    spi_ok = test_spi_interface(display_lines)
    waveshare_ok = test_waveshare_library(display_lines)
    
    # Only test display if prerequisites are met
    if spi_ok and waveshare_ok:
        display, draw, image = test_display(display_lines, font)
    else:
        print("\n*** SKIPPING DISPLAY TEST ***")
        print("SPI or Waveshare library issues detected. Fix these first.")
        display, draw, image = None, None, None
        display_lines.append("Display: SKIPPED")
    
    test_audio_devices(display_lines)
    test_speaker(display_lines)
    test_microphone(display_lines)
    test_motion_sensor(display_lines)

    if display:
        print_header("Finalizing Display")
        print("Sending final summary to the e-Paper display...")
        update_display(display, draw, image, font, display_lines)
        print("Display update complete (refresh may take ~3.5 seconds).")
        
        # Clean up display resources
        try:
            if hasattr(display, 'cleanup'):
                display.cleanup()
                print("Display resources cleaned up.")
        except Exception as e:
            print(f"Warning: Failed to cleanup display: {e}")

    print_header("Diagnostic Complete")
    print("You can now restart the main service with: sudo systemctl start fridgepinventory.service")
    if not display:
        print("\nDisplay test failed. Cannot proceed with other tests that require display feedback.")
        print("Please run the individual tests for audio and motion if needed.")
