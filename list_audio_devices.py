# list_audio_devices.py
import pyaudio
import sys

print("--- Audio Device Lister ---")

# This script lists all available audio input devices that PyAudio can detect.
# Run this on your Raspberry Pi to find the correct 'device_index' for your microphone.

pa = None
try:
    pa = pyaudio.PyAudio()
    print("Successfully initialized PyAudio.")
    print("\nSearching for available audio input devices...\n")

    found_devices = False
    for i in range(pa.get_device_count()):
        device_info = pa.get_device_info_by_index(i)
        # Check if the device has input channels (i.e., it's a microphone)
        if device_info.get('maxInputChannels') > 0:
            found_devices = True
            print(f"-----------------------------------------------------")
            print(f"  Device Index: {device_info.get('index')}")
            print(f"  Name: {device_info.get('name')}")
            print(f"  Input Channels: {device_info.get('maxInputChannels')}")
            print(f"  Default Sample Rate: {device_info.get('defaultSampleRate')}")
            print(f"-----------------------------------------------------\n")

    if not found_devices:
        print("\n--- No audio input devices found. ---")
        print("Troubleshooting:")
        print("  - Ensure your microphone is securely connected.")
        print("  - If using a USB microphone, try a different USB port.")
        print("  - Check 'lsusb' to see if the system detects the USB device.")

    else:
        print("\n--- ACTION REQUIRED ---")
        print("1. Identify your microphone in the list above.")
        print("2. Note its 'Device Index'.")
        print("3. Open 'config.yaml' and set 'audio.voice_recognition.device_index' to that number.")
        print("   Example: device_index: 2")
        print("4. Restart the fridgepinventory.service.")

except Exception as e:
    print(f"\n--- An error occurred ---", file=sys.stderr)
    print(f"Error: {e}", file=sys.stderr)
    print("This might happen if PyAudio or its dependency 'portaudio' is not installed correctly.", file=sys.stderr)
    sys.exit(1)

finally:
    if pa:
        pa.terminate()
        print("\nPyAudio terminated.")
