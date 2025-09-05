# Voice recognition manager with proper encapsulation

import logging
import traceback
import threading
from typing import Optional
import speech_recognition as sr
from .config_manager import config

# Optional PyAudio dependency
try:
    import pyaudio
except Exception:
    pyaudio = None

class VoiceRecognitionManager:
    """Manages voice recognition with proper encapsulation and error recovery."""
    
    MAX_RETRIES = 3
    
    def __init__(self, config_manager=None):
        """Initialize voice recognition manager.
        
        Args:
            config_manager: Configuration manager instance.
        """
        self._config = config_manager or config
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # Component instances
        self._recognizer = None
        self._microphone = None
        self._pyaudio_instance = None
        
        # State tracking
        self._initialization_failed = False
        self._retry_count = 0
        self._nlp_model = None
    
    def _initialize_recognizer(self) -> bool:
        """Initialize the speech recognizer."""
        if self._recognizer is not None:
            return True
        
        try:
            self._recognizer = sr.Recognizer()
            
            # Configure recognizer settings
            audio_config = self._config.get_audio_config()
            voice_config = audio_config.get('voice_recognition', {})
            
            # Set energy threshold for better noise handling
            energy_threshold = voice_config.get('energy_threshold', 4000)
            if isinstance(energy_threshold, (int, float)) and energy_threshold > 0:
                self._recognizer.energy_threshold = energy_threshold
            
            # Set pause threshold
            pause_threshold = voice_config.get('pause_threshold', 0.8)
            if isinstance(pause_threshold, (int, float)) and pause_threshold > 0:
                self._recognizer.pause_threshold = pause_threshold
            
            self.logger.info("Speech recognizer initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize recognizer: {e}")
            self._recognizer = None
            return False
    
    def _initialize_pyaudio(self):
        """Initialize PyAudio for device enumeration (optional)."""
        if self._pyaudio_instance is not None or pyaudio is None:
            return
        
        try:
            self._pyaudio_instance = pyaudio.PyAudio()
            self._log_audio_devices()
        except Exception as e:
            self.logger.warning(f"PyAudio initialization failed (non-fatal): {e}")
            self._pyaudio_instance = None
    
    def _log_audio_devices(self):
        """Log available audio devices."""
        if not self._pyaudio_instance:
            return
        
        try:
            device_count = self._pyaudio_instance.get_device_count()
            self.logger.info(f"Found {device_count} audio devices")
            
            for i in range(device_count):
                try:
                    device_info = self._pyaudio_instance.get_device_info_by_index(i)
                    if device_info.get('maxInputChannels', 0) > 0:
                        self.logger.info(
                            f"  Input Device {i}: {device_info.get('name')}, "
                            f"Channels: {device_info.get('maxInputChannels')}"
                        )
                except Exception:
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error enumerating audio devices: {e}")
    
    def _initialize_microphone(self) -> bool:
        """Initialize the microphone."""
        if self._microphone is not None:
            return True
        
        try:
            # Get audio configuration
            audio_config = self._config.get_audio_config()
            voice_config = audio_config.get('voice_recognition', {})
            device_index = voice_config.get('device_index')
            
            # Validate and use device index if specified
            if device_index is not None:
                if isinstance(device_index, int) and device_index >= 0:
                    self._microphone = sr.Microphone(device_index=device_index)
                    self.logger.info(f"Using microphone device index: {device_index}")
                else:
                    self.logger.warning(f"Invalid device_index {device_index}, using default")
                    self._microphone = sr.Microphone()
            else:
                self._microphone = sr.Microphone()
                self.logger.info("Using default system microphone")
            
            # Test the microphone
            with self._microphone as source:
                if self._recognizer:
                    self._recognizer.adjust_for_ambient_noise(source, duration=1)
            
            self.logger.info("Microphone initialized and calibrated")
            self._retry_count = 0  # Reset on success
            return True
            
        except OSError as e:
            self.logger.error(f"Microphone device not available: {e}")
            self._handle_initialization_failure()
            return False
        except Exception as e:
            self.logger.error(f"Failed to initialize microphone: {e}")
            self._handle_initialization_failure()
            return False
    
    def _handle_initialization_failure(self):
        """Handle initialization failure with retry logic."""
        self._microphone = None
        self._retry_count += 1
        
        if self._retry_count >= self.MAX_RETRIES:
            self._initialization_failed = True
            self.logger.error(f"Audio initialization failed after {self.MAX_RETRIES} attempts")
    
    def initialize(self) -> bool:
        """Initialize all audio components."""
        with self._lock:
            # Check if permanently failed
            if self._initialization_failed:
                self.logger.debug("Audio initialization previously failed permanently")
                return False
            
            # Initialize recognizer
            if not self._initialize_recognizer():
                return False
            
            # Initialize PyAudio (optional)
            self._initialize_pyaudio()
            
            # Initialize microphone
            if not self._initialize_microphone():
                return False
            
            return True
    
    def recognize_speech(self) -> Optional[str]:
        """Recognize speech from the microphone.
        
        Returns:
            Recognized text or None if failed.
        """
        # Check if permanently failed
        if self._initialization_failed:
            self.logger.debug("Audio initialization permanently failed")
            return None
        
        # Initialize if needed
        if not self.initialize():
            self.logger.error("Failed to initialize audio components")
            return None
        
        self.logger.info("Listening for command...")
        
        # Get configuration
        audio_config = self._config.get_audio_config()
        voice_config = audio_config.get('voice_recognition', {})
        
        # Validate timeout values
        timeout = voice_config.get('timeout', 5)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            timeout = 5
        
        phrase_time_limit = voice_config.get('phrase_time_limit', 10)
        if not isinstance(phrase_time_limit, (int, float)) or phrase_time_limit <= 0:
            phrase_time_limit = 10
        
        # Capture audio
        audio_data = None
        try:
            with self._microphone as source:
                self.logger.debug("Listening with microphone...")
                audio_data = self._recognizer.listen(
                    source, 
                    timeout=timeout, 
                    phrase_time_limit=phrase_time_limit
                )
            self.logger.info("Audio captured successfully")
            
        except sr.WaitTimeoutError:
            self.logger.warning("No speech detected within timeout period")
            return None
        except OSError as e:
            self.logger.error(f"Microphone error: {e}")
            self._microphone = None  # Force re-initialization
            return None
        except Exception as e:
            self.logger.error(f"Error capturing audio: {e}")
            return None
        
        if audio_data is None:
            return None
        
        # Try recognition with fallback engines
        return self._recognize_with_fallback(audio_data, voice_config)
    
    def _recognize_with_fallback(self, audio_data, voice_config) -> Optional[str]:
        """Try recognition with multiple engines as fallback.
        
        Args:
            audio_data: Captured audio data.
            voice_config: Voice recognition configuration.
            
        Returns:
            Recognized text or None.
        """
        engine = voice_config.get('engine', 'sphinx')
        engines_to_try = []
        
        # Build engine list based on configuration
        if engine.lower() == 'google':
            engines_to_try.append(('google', self._recognizer.recognize_google))
            if voice_config.get('enable_sphinx_fallback', True):
                engines_to_try.append(('sphinx', self._recognizer.recognize_sphinx))
        else:
            engines_to_try.append(('sphinx', self._recognizer.recognize_sphinx))
            if voice_config.get('enable_google_fallback', False):
                engines_to_try.append(('google', self._recognizer.recognize_google))
        
        # Try each engine
        for engine_name, recognize_func in engines_to_try:
            try:
                self.logger.info(f"Attempting recognition with {engine_name} engine")
                command = recognize_func(audio_data)
                self.logger.info(f"Recognized with {engine_name}: {command}")
                return command.lower()
                
            except sr.UnknownValueError:
                self.logger.warning(f"{engine_name} engine could not understand audio")
                continue
            except sr.RequestError as e:
                self.logger.error(f"{engine_name} engine request failed: {e}")
                continue
            except Exception as e:
                self.logger.error(f"Unexpected error with {engine_name}: {e}")
                continue
        
        self.logger.warning("All recognition engines failed")
        return None
    
    def cleanup(self):
        """Clean up audio resources."""
        with self._lock:
            try:
                if self._microphone:
                    self.logger.info("Cleaning up microphone")
                    self._microphone = None
                
                if self._pyaudio_instance:
                    self.logger.info("Terminating PyAudio")
                    self._pyaudio_instance.terminate()
                    self._pyaudio_instance = None
                
                # Reset state
                self._recognizer = None
                self._initialization_failed = False
                self._retry_count = 0
                
                self.logger.info("Audio cleanup completed")
                
            except Exception as e:
                self.logger.error(f"Error during audio cleanup: {e}")

# Create default instance for backward compatibility
_default_manager = None

def get_default_voice_recognition_manager():
    """Get the default voice recognition manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = VoiceRecognitionManager()
    return _default_manager

# Backward compatibility function
def recognize_speech_from_mic() -> Optional[str]:
    """Recognize speech using the default manager."""
    return get_default_voice_recognition_manager().recognize_speech()

def cleanup_audio():
    """Clean up the default manager."""
    get_default_voice_recognition_manager().cleanup()
