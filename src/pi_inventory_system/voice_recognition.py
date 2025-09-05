# Module for handling voice commands

import speech_recognition as sr
import logging
import traceback
from .config_manager import config

logger = logging.getLogger(__name__)

# Optional PyAudio dependency (used for device listing); not required for basic mic usage
try:
    import pyaudio  # type: ignore
except Exception:
    pyaudio = None  # type: ignore

# Global recognizer and microphone instances
recognizer = None
microphone = None
pyaudio_instance = None  # Keep a reference to PyAudio instance for optional device logging
_initialization_failed = False  # Track if initialization has permanently failed
_retry_count = 0  # Track retry attempts
MAX_RETRIES = 3  # Maximum number of initialization retries

def _initialize_audio_components():
    global recognizer, microphone, pyaudio_instance, _initialization_failed, _retry_count
    
    # Check if we've already failed too many times
    if _initialization_failed:
        logger.debug("Audio initialization previously failed permanently, not retrying")
        return False
    
    logger.info("Initializing audio components for voice recognition...")

    if recognizer is None:
        try:
            logger.debug("Initializing sr.Recognizer().")
            recognizer = sr.Recognizer()
            # Configure recognizer settings
            audio_config = config.get_audio_config()
            voice_config = audio_config.get('voice_recognition', {})
            
            # Set energy threshold for better noise handling
            energy_threshold = voice_config.get('energy_threshold', 4000)
            recognizer.energy_threshold = energy_threshold
            
            # Set pause threshold
            pause_threshold = voice_config.get('pause_threshold', 0.8)
            recognizer.pause_threshold = pause_threshold
        except Exception as e:
            logger.error(f"Failed to initialize recognizer: {e}")
            recognizer = None
            return False
    
    if pyaudio_instance is None and pyaudio is not None:
        try:
            logger.debug("Initializing pyaudio.PyAudio() instance for optional device logging.")
            pyaudio_instance = pyaudio.PyAudio()
            _log_audio_devices(pyaudio_instance)  # Best-effort logging; not required
        except Exception as e:
            logger.warning(f"PyAudio initialization failed or unavailable: {e}")
            logger.debug(traceback.format_exc())
            pyaudio_instance = None  # Non-fatal

    if microphone is None:
        try:
            logger.info("Initializing sr.Microphone(). This may take a moment...")
            # Get audio configuration
            audio_config = config.get_audio_config()
            voice_config = audio_config.get('voice_recognition', {})
            device_index = voice_config.get('device_index')
            
            # Initialize microphone with configured device index if specified
            if device_index is not None:
                # Validate device index
                if not isinstance(device_index, int) or device_index < 0:
                    logger.warning(f"Invalid device_index {device_index}, using default")
                    device_index = None
                else:
                    microphone = sr.Microphone(device_index=device_index)
                    logger.info(f"Using configured microphone device index: {device_index}")
            
            if device_index is None:
                microphone = sr.Microphone()
                logger.info("Using default system microphone")
            
            logger.info("sr.Microphone() initialized.")
            
            # Test opening the stream briefly to catch immediate errors
            logger.debug("Adjusting for ambient noise...")
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source, duration=1) # Reduced duration for faster init
            logger.info("Microphone initialized and adjusted for ambient noise.")
            
            # Reset retry count on success
            _retry_count = 0
            
        except OSError as e:
            # Handle device not available errors
            logger.error(f"Microphone device not available: {e}")
            microphone = None
            _retry_count += 1
            if _retry_count >= MAX_RETRIES:
                _initialization_failed = True
                logger.error(f"Audio initialization failed after {MAX_RETRIES} attempts, giving up")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize sr.Microphone or adjust_for_ambient_noise: {e}")
            logger.error(traceback.format_exc())
            microphone = None
            _retry_count += 1
            if _retry_count >= MAX_RETRIES:
                _initialization_failed = True
                logger.error(f"Audio initialization failed after {MAX_RETRIES} attempts, giving up")
            return False
    
    return recognizer is not None and microphone is not None

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
    """Recognize speech from the microphone with improved error recovery."""
    global recognizer, microphone, _initialization_failed

    # Check if permanently failed
    if _initialization_failed:
        logger.debug("Audio initialization permanently failed, returning None")
        return None

    if not _initialize_audio_components():
        logger.error("Audio components not initialized. Cannot recognize speech.")
        return None

    logger.info("Listening for command...")
    
    # Get audio configuration for timeouts and engine
    audio_config = config.get_audio_config()
    voice_config = audio_config.get('voice_recognition', {})
    timeout = voice_config.get('timeout', 5)
    phrase_time_limit = voice_config.get('phrase_time_limit', 10)
    engine = voice_config.get('engine', 'sphinx')
    
    # Validate configuration values
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        timeout = 5
        logger.warning(f"Invalid timeout value, using default: {timeout}")
    
    if not isinstance(phrase_time_limit, (int, float)) or phrase_time_limit <= 0:
        phrase_time_limit = 10
        logger.warning(f"Invalid phrase_time_limit value, using default: {phrase_time_limit}")
    
    audio_data = None
    
    try:
        with microphone as source:
            logger.debug("Microphone source opened, calling recognizer.listen().")
            audio_data = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        logger.info("Audio captured, attempting recognition...")
        
    except sr.WaitTimeoutError:
        logger.warning("No speech detected within timeout period.")
        return None
    except OSError as e:
        # Handle microphone disconnection or failure
        logger.error(f"Microphone error during listening: {e}")
        # Reset microphone to force re-initialization on next attempt
        microphone = None
        return None
    except Exception as e:
        logger.error(f"Error capturing audio: {e}")
        logger.error(traceback.format_exc())
        return None
    
    if audio_data is None:
        logger.warning("No audio data captured")
        return None
    
    # Try recognition with multiple engines as fallback
    command = None
    engines_to_try = []
    
    if engine.lower() == 'google':
        engines_to_try = [('google', recognizer.recognize_google), 
                         ('sphinx', recognizer.recognize_sphinx)]
    else:
        engines_to_try = [('sphinx', recognizer.recognize_sphinx)]
        # Only add Google as fallback if network is likely available
        if voice_config.get('enable_google_fallback', False):
            engines_to_try.append(('google', recognizer.recognize_google))
    
    for engine_name, recognize_func in engines_to_try:
        try:
            logger.info(f"Attempting recognition with {engine_name} engine")
            command = recognize_func(audio_data)
            logger.info(f"Voice command recognized with {engine_name}: {command}")
            return command.lower()
            
        except sr.UnknownValueError:
            logger.warning(f"{engine_name} engine could not understand audio")
            continue
            
        except sr.RequestError as e:
            logger.error(f"{engine_name} engine request failed: {e}")
            if engine_name == 'google':
                logger.info("Network may be unavailable, will use offline engine only")
            continue
            
        except Exception as e:
            logger.error(f"Unexpected error with {engine_name} engine: {e}")
            logger.error(traceback.format_exc())
            continue
    
    # All engines failed
    logger.warning("All recognition engines failed to understand the audio")
    return None

def cleanup_audio():
    """Clean up audio resources."""
    global pyaudio_instance, microphone, recognizer, _initialization_failed, _retry_count
    
    try:
        if microphone:
            logger.info("Cleaning up microphone resources")
            microphone = None
        
        if pyaudio_instance:
            logger.info("Terminating PyAudio instance")
            pyaudio_instance.terminate()
            pyaudio_instance = None
        
        # Reset state for potential restart
        recognizer = None
        _initialization_failed = False
        _retry_count = 0
        
        logger.info("Audio cleanup completed")
    except Exception as e:
        logger.error(f"Error during audio cleanup: {e}")
