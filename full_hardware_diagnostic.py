# full_hardware_diagnostic.py

### 
### Run with:
### source ~/.inky_venv/bin/activate && python3 full_hardware_diagnostic.py
### 

import time
import os
import sys
import subprocess

# --- Test Configuration ---
MOTION_SENSOR_PIN = 4
MIC_TEST_DURATION = 3  # seconds
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
        draw.rectangle((0, 0, display.width, display.height), fill=display.WHITE)
        y = 5
        for line in lines:
            draw.text((5, y), line, font=font, fill=display.BLACK)
            y += font.getbbox('A')[3] + 2 # Height of font + 2px padding
        display.set_image(image)
        display.show()

# --- Test Functions ---

def test_display(lines, font):
    print_header("Display Test")
    try:
        from inky.auto import auto
        from PIL import Image, ImageDraw
        display = auto(verbose=True)
        image = Image.new("P", (display.width, display.height))
        draw = ImageDraw.Draw(image)
        print_status("Inky display initialized", True)
        lines.append("Display: OK")
        update_display(display, draw, image, font, lines)
        return display, draw, image
    except Exception as e:
        print_status(f"Inky display initialization failed: {e}", False)
        lines.append("Display: FAIL")
        return None, None, None

def test_audio_devices(lines, display, draw, image, font):
    print_header("Audio Device Listing")
    try:
        import pyaudio
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
    update_display(display, draw, image, font, lines)

def test_speaker(lines, display, draw, image, font):
    print_header("Speaker Test")
    try:
        from playsound import playsound
        # Assumes a success.wav file exists as in the main project
        sound_file = os.path.join(os.path.dirname(__file__), 'assets', 'sounds', 'success.wav')
        if not os.path.exists(sound_file):
            raise FileNotFoundError("success.wav not found in assets/sounds")
        print("Playing test sound...", end="", flush=True)
        playsound(sound_file)
        print(" Done.")
        print_status("Speaker test successful", True)
        lines.append("Speaker: OK")
    except Exception as e:
        print_status(f"Speaker test failed: {e}", False)
        lines.append("Speaker: FAIL")
    update_display(display, draw, image, font, lines)


def test_microphone(lines, display, draw, image, font):
    print_header("Microphone Test")
    try:
        import pyaudio
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
        # A very basic check to see if audio is not just silence
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
    update_display(display, draw, image, font, lines)

def test_motion_sensor(lines, display, draw, image, font):
    print_header("Motion Sensor Test")
    try:
        from pi_inventory_system.motion_sensor import detect_motion, cleanup
        print("Please wave your hand in front of the sensor for 5 seconds...")
        motion_detected = False
        for i in range(10):
            if detect_motion():
                motion_detected = True
                break
            time.sleep(0.5)
            print(".", end="", flush=True)
        print()
        print_status("Motion sensor check", motion_detected)
        lines.append(f"Motion: {'OK' if motion_detected else 'FAIL'}")
        cleanup()
    except Exception as e:
        print_status(f"Motion sensor test failed: {e}", False)
        lines.append("Motion: FAIL")
    update_display(display, draw, image, font, lines)

# --- Main Execution ---
if __name__ == "__main__":
    # Stop the main service to avoid pin conflicts
    print("Attempting to stop 'fridgepinventory.service' to free up hardware...")
    subprocess.run(["sudo", "systemctl", "stop", "fridgepinventory.service"], check=False)
    time.sleep(1) # Give service time to stop

    # Load a font for the display
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except IOError:
        font = ImageFont.load_default()

    display_lines = ["Hardware Diagnostic:"]
    display, draw, image = test_display(display_lines, font)
    
    if display: # Only run other tests if display is working
        test_audio_devices(display_lines, display, draw, image, font)
        test_speaker(display_lines, display, draw, image, font)
        test_microphone(display_lines, display, draw, image, font)
        test_motion_sensor(display_lines, display, draw, image, font)

        print_header("Diagnostic Complete")
        print("Check the eInk display for a summary.")
        print("You can now restart the main service with: sudo systemctl start fridgepinventory.service")
    else:
        print("\nDisplay test failed. Cannot proceed with other tests that require display feedback.")
        print("Please run the individual tests for audio and motion if needed.")
