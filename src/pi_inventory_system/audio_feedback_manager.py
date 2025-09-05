# Thread-safe audio feedback manager

import logging
import os
import threading
import queue
import time
from typing import Optional
from .config_manager import config

logger = logging.getLogger(__name__)

# Try to import optional audio libraries
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    from playsound import playsound
    PLAYSOUND_AVAILABLE = True
except ImportError:
    PLAYSOUND_AVAILABLE = False


class AudioFeedbackManager:
    """Thread-safe audio feedback manager with circuit breaker pattern."""
    
    def __init__(self, config_manager=None):
        """Initialize audio feedback manager.
        
        Args:
            config_manager: Configuration manager instance.
        """
        self._config = config_manager or config
        self._lock = threading.Lock()
        self._sound_lock = threading.Lock()
        
        # TTS components
        self._tts_engine = None
        self._tts_queue = queue.Queue()
        self._tts_thread = None
        self._shutdown_event = threading.Event()
        
        # Circuit breaker for TTS
        self._tts_failures = 0
        self._tts_disabled = False
        self._max_failures = 3
        
        # Circuit breaker for sounds
        self._sound_failures = 0
        self._sound_disabled = False
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize TTS if available
        if PYTTSX3_AVAILABLE:
            self._initialize_tts()
    
    def _initialize_tts(self) -> bool:
        """Initialize the TTS engine."""
        with self._lock:
            if self._tts_disabled:
                return False
                
            if self._tts_engine is not None:
                return True
            
            try:
                self.logger.info("Initializing TTS engine...")
                self._tts_engine = pyttsx3.init()
                
                # Configure TTS from config
                audio_config = self._config.get_audio_config()
                tts_config = audio_config.get('text_to_speech', {})
                
                rate = tts_config.get('rate', 150)
                volume = tts_config.get('volume', 0.9)
                voice_id = tts_config.get('voice_id')
                
                self._tts_engine.setProperty('rate', rate)
                self._tts_engine.setProperty('volume', volume)
                if voice_id:
                    self._tts_engine.setProperty('voice', voice_id)
                
                # Start worker thread
                self._start_tts_worker()
                
                self.logger.info(f"TTS initialized with rate={rate}, volume={volume}")
                self._tts_failures = 0  # Reset on success
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to initialize TTS: {e}")
                self._handle_tts_failure()
                return False
    
    def _handle_tts_failure(self):
        """Handle TTS failure with circuit breaker."""
        self._tts_failures += 1
        if self._tts_failures >= self._max_failures:
            self._tts_disabled = True
            self.logger.error(f"TTS disabled after {self._max_failures} failures")
            self._tts_engine = None
    
    def _handle_sound_failure(self):
        """Handle sound playback failure with circuit breaker."""
        self._sound_failures += 1
        if self._sound_failures >= self._max_failures:
            self._sound_disabled = True
            self.logger.error(f"Sound playback disabled after {self._max_failures} failures")
    
    def _start_tts_worker(self):
        """Start the TTS worker thread."""
        if self._tts_thread and self._tts_thread.is_alive():
            return
        
        self._tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self._tts_thread.start()
        self.logger.debug("Started TTS worker thread")
    
    def _tts_worker(self):
        """Worker thread for processing TTS queue."""
        while not self._shutdown_event.is_set():
            try:
                # Wait for message with timeout
                message = self._tts_queue.get(timeout=1.0)
                
                if message is None:  # Shutdown signal
                    break
                
                # Process TTS
                with self._lock:
                    if self._tts_engine and not self._tts_disabled:
                        try:
                            self._tts_engine.say(message)
                            self._tts_engine.runAndWait()
                            self.logger.debug(f"TTS spoke: {message}")
                            self._tts_failures = 0  # Reset on success
                        except Exception as e:
                            self.logger.error(f"TTS error: {e}")
                            self._handle_tts_failure()
                            
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"TTS worker error: {e}")
    
    def speak(self, message: str) -> bool:
        """Speak a message using TTS.
        
        Args:
            message: Message to speak.
            
        Returns:
            True if message was queued successfully.
        """
        if not message:
            return False
        
        if not PYTTSX3_AVAILABLE or self._tts_disabled:
            # Fallback to print
            print(f"[TTS]: {message}")
            return True
        
        if not self._initialize_tts():
            print(f"[TTS]: {message}")
            return True
        
        try:
            self._tts_queue.put(message, timeout=1.0)
            self.logger.debug(f"Queued TTS message: {message}")
            return True
        except queue.Full:
            self.logger.warning("TTS queue full, message dropped")
            return False
        except Exception as e:
            self.logger.error(f"Error queueing TTS: {e}")
            return False
    
    def play_sound(self, sound_type: str) -> bool:
        """Play a feedback sound.
        
        Args:
            sound_type: Type of sound ('success', 'error', 'warning').
            
        Returns:
            True if sound was played or printed.
        """
        if self._sound_disabled or not PLAYSOUND_AVAILABLE:
            # Fallback to print
            print(f"[Sound]: {sound_type}")
            return True
        
        with self._sound_lock:
            try:
                # Get sound configuration
                audio_config = self._config.get_audio_config()
                sound_config = audio_config.get('feedback_sounds', {})
                
                # Get sound file path
                sound_map = {
                    'success': sound_config.get('success_sound', 'sounds/success.wav'),
                    'error': sound_config.get('error_sound', 'sounds/error.wav'),
                    'warning': sound_config.get('warning_sound', 'sounds/warning.wav')
                }
                
                sound_file = sound_map.get(sound_type)
                if not sound_file:
                    self.logger.warning(f"Unknown sound type: {sound_type}")
                    return False
                
                # Make path absolute if needed
                if not os.path.isabs(sound_file):
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
                    sound_file = os.path.join(project_root, 'assets', sound_file)
                
                # Check if file exists
                if not os.path.exists(sound_file):
                    self.logger.warning(f"Sound file not found: {sound_file}")
                    print(f"[Sound]: {sound_type}")
                    return True
                
                # Play sound
                playsound(sound_file)
                self.logger.debug(f"Played {sound_type} sound: {sound_file}")
                self._sound_failures = 0  # Reset on success
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to play sound: {e}")
                self._handle_sound_failure()
                print(f"[Sound]: {sound_type}")
                return True
    
    def output_confirmation(self, message: str) -> bool:
        """Output confirmation with TTS and sound.
        
        Args:
            message: Confirmation message.
            
        Returns:
            True if output was successful.
        """
        success = True
        
        if message:
            success = self.speak(message) and success
        
        success = self.play_sound('success') and success
        return success
    
    def output_error(self, message: str) -> bool:
        """Output error with TTS and sound.
        
        Args:
            message: Error message.
            
        Returns:
            True if output was successful.
        """
        success = True
        
        if message:
            success = self.speak(message) and success
        
        success = self.play_sound('error') and success
        return success
    
    def cleanup(self):
        """Clean up audio resources."""
        self.logger.info("Cleaning up audio feedback manager")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Send shutdown signal to queue
        if self._tts_queue:
            try:
                self._tts_queue.put(None, timeout=0.1)
            except Exception:
                pass
        
        # Wait for thread to finish
        if self._tts_thread and self._tts_thread.is_alive():
            self._tts_thread.join(timeout=2.0)
        
        # Clean up TTS engine
        with self._lock:
            if self._tts_engine:
                try:
                    self._tts_engine.stop()
                    self.logger.info("TTS engine stopped")
                except Exception as e:
                    self.logger.error(f"Error stopping TTS: {e}")
                self._tts_engine = None
        
        self.logger.info("Audio feedback cleanup completed")


# Backward compatibility wrapper
class AudioFeedback:
    """Backward compatibility wrapper for AudioFeedbackManager."""
    
    def __init__(self):
        self._manager = AudioFeedbackManager()
    
    def play_sound(self, sound_type: str) -> bool:
        return self._manager.play_sound(sound_type)
    
    def speak(self, message: str) -> bool:
        return self._manager.speak(message)
    
    def cleanup(self):
        self._manager.cleanup()
