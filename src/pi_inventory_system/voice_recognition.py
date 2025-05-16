# Module for handling voice commands

import speech_recognition as sr
import logging
import traceback
import pyaudio # Explicitly import pyaudio to access its methods for device listing

logger = logging.getLogger(__name__)

# Global recognizer and microphone instances
recognizer = None
microphone = None
pyaudio_instance = None # Keep a reference to PyAudio instance for proper termination

def _initialize_audio_components():
    global recognizer, microphone, pyaudio_instance
    logger.info("Initializing audio components for voice recognition...")

    if recognizer is None:
        logger.debug("Initializing sr.Recognizer().")
        recognizer = sr.Recognizer()
    
    if pyaudio_instance is None:
        try:
            logger.debug("Initializing pyaudio.PyAudio() instance.")
            pyaudio_instance = pyaudio.PyAudio()
            logger.info("PyAudio instance created successfully.")
            _log_audio_devices(pyaudio_instance) # Log available devices
        except Exception as e:
            logger.error(f"Failed to initialize PyAudio: {e}")
            logger.error(traceback.format_exc())
            pyaudio_instance = None # Ensure it's None if failed
            return False # Cannot proceed without PyAudio

    if microphone is None and pyaudio_instance is not None:
        try:
            # Log settings before attempting to open microphone
            # Common settings: device_index (if not default), sample_rate, chunk_size
            # If you use a specific device_index, log it here.
            logger.info("Initializing sr.Microphone(). This may take a moment...")
            # You might need to specify a device_index if the default is not correct:
            # microphone = sr.Microphone(device_index=YOUR_DEVICE_INDEX, sample_rate=16000) 
            # If unsure, sr.Microphone() tries to use the default system microphone.
            microphone = sr.Microphone() 
            logger.info("sr.Microphone() initialized.")
            # Test opening the stream briefly to catch immediate errors
            logger.debug("Adjusting for ambient noise...")
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source, duration=1) # Reduced duration for faster init
            logger.info("Microphone initialized and adjusted for ambient noise.")
        except Exception as e:
            logger.error(f"Failed to initialize sr.Microphone or adjust_for_ambient_noise: {e}")
            logger.error(traceback.format_exc())
            microphone = None # Ensure it's None if failed
            return False
    return recognizer is not None and microphone is not None and pyaudio_instance is not None

def _log_audio_devices(pa_instance):
    if not pa_instance:
        logger.warning("PyAudio instance not available, cannot log audio devices.")
        return
    logger.info("Available Pyaudio/PortAudio devices:")
    try:
        default_host_api_info = pa_instance.get_default_host_api_info()
        logger.info(f"Default Host API: {default_host_api_info.get('name')}, Index: {default_host_api_info.get('index')}, Devices: {default_host_api_info.get('deviceCount')}")
        default_input_device_info = pa_instance.get_default_input_device_info()
        logger.info(f"Default Input Device: {default_input_device_info.get('name')}, Index: {default_input_device_info.get('index')}")
        default_output_device_info = pa_instance.get_default_output_device_info()
        logger.info(f"Default Output Device: {default_output_device_info.get('name')}, Index: {default_output_device_info.get('index')}")
        
        device_count = pa_instance.get_device_count()
        logger.info(f"Total Pyaudio devices found: {device_count}")
        for i in range(device_count):
            device_info = pa_instance.get_device_info_by_index(i)
            logger.info(
                f"  Device {i}: {device_info.get('name')}, "
                f"Input Channels: {device_info.get('maxInputChannels')}, "
                f"Output Channels: {device_info.get('maxOutputChannels')}, "
                f"Default Sample Rate: {device_info.get('defaultSampleRate')}, "
                f"Host API Index: {device_info.get('hostApi')}"
            )
    except Exception as e:
        logger.error(f"Error enumerating Pyaudio devices: {e}")
        logger.error(traceback.format_exc())

def recognize_speech_from_mic():
    """Recognize speech from the microphone."""
    global recognizer, microphone

    if not _initialize_audio_components():
        logger.error("Audio components not initialized. Cannot recognize speech.")
        return "Error: Microphone not initialized."

    logger.info("Listening for command...")
    try:
        with microphone as source:
            # recognizer.adjust_for_ambient_noise(source) # Moved to init, or can be done less frequently
            logger.debug("Microphone source opened, calling recognizer.listen().")
            audio_data = recognizer.listen(source, timeout=5, phrase_time_limit=10) # Added timeout
        logger.info("Audio captured, attempting recognition...")
        # Using PocketSphinx for offline recognition by default
        # Other options: recognize_google, recognize_bing, etc. (require internet and API keys)
        command = recognizer.recognize_sphinx(audio_data) # Default to sphinx for offline
        # command = recognizer.recognize_google(audio_data) # Example for Google Web Speech API
        logger.info(f"Voice command recognized: {command}")
        return command.lower()
    except sr.WaitTimeoutError:
        logger.warning("No speech detected within timeout period.")
        return ""
    except sr.UnknownValueError:
        logger.warning("Speech Recognition could not understand audio.")
        return ""
    except sr.RequestError as e:
        logger.error(f"Speech Recognition service request failed: {e}")
        logger.error(traceback.format_exc())
        return f"Error: SR request failed - {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred during speech recognition: {e}")
        logger.error(traceback.format_exc())
        return f"Error: {e}"

# Optional: Function to clean up PyAudio if needed, though SpeechRecognition usually handles it.
# def cleanup_pyaudio():
#     global pyaudio_instance
#     if pyaudio_instance:
#         logger.info("Terminating PyAudio instance.")
#         pyaudio_instance.terminate()
#         pyaudio_instance = None
