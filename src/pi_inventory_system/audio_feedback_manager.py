# Thread-safe audio feedback manager

import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from typing import Optional

from .config_manager import get_default_config_manager


logger = logging.getLogger(__name__)

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    import simpleaudio
    SIMPLEAUDIO_AVAILABLE = True
except ImportError:
    SIMPLEAUDIO_AVAILABLE = False


def _play_wav_file(path: str) -> None:
    """Play a WAV file via simpleaudio if available, else fall back to aplay."""
    if SIMPLEAUDIO_AVAILABLE:
        wave_obj = simpleaudio.WaveObject.from_wave_file(path)
        wave_obj.play().wait_done()
        return
    aplay = shutil.which("aplay")
    if aplay:
        # Bounded so a wedged ALSA device cannot hold the sound lock forever.
        subprocess.run([aplay, "-q", path], check=True, timeout=10)
        return
    raise RuntimeError("No WAV playback backend available (simpleaudio or aplay)")


class AudioFeedbackManager:
    """Thread-safe audio feedback manager with circuit breaker pattern."""
    
    def __init__(self, config_manager=None):
        """Initialize audio feedback manager.
        
        Args:
            config_manager: Configuration manager instance.
        """
        self._config = config_manager or get_default_config_manager()
        self._lock = threading.Lock()
        self._sound_lock = threading.Lock()
        
        # TTS components
        self._tts_engine = None
        self._tts_queue = queue.Queue(maxsize=10)
        self._tts_thread = None
        self._shutdown_event = threading.Event()
        
        # Circuit breaker for TTS
        self._tts_failures = 0
        self._tts_disabled = False
        self._max_failures = 3
        
        # Circuit breaker for sounds
        self._sound_failures = 0
        self._sound_disabled = False

        # Half-duplex bookkeeping: count queued/playing outputs so the voice
        # loop can avoid listening to our own chimes and TTS through the mic.
        self._output_lock = threading.Lock()
        self._active_outputs = 0
        self._last_output_ended_at: Optional[float] = None
        
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

    def reset_circuit_breakers(self) -> None:
        """Re-enable both TTS and sound paths after a transient failure burst.

        Called after startup diagnostics so a flaky boot-time WAV play does
        not silence the rest of the session.
        """
        with self._lock, self._sound_lock:
            self._tts_failures = 0
            self._tts_disabled = False
            self._sound_failures = 0
            self._sound_disabled = False
            self.logger.info("Audio circuit breakers reset")
    
    def _begin_output(self):
        with self._output_lock:
            self._active_outputs += 1

    def _end_output(self):
        with self._output_lock:
            self._active_outputs = max(0, self._active_outputs - 1)
            self._last_output_ended_at = time.monotonic()

    def is_output_active(self, grace: float = 0.0) -> bool:
        """True while feedback audio is queued or playing, or within `grace`
        seconds of the last output finishing (covers speaker/echo decay)."""
        with self._output_lock:
            if self._active_outputs > 0:
                return True
            if self._last_output_ended_at is None:
                return False
            return (time.monotonic() - self._last_output_ended_at) < grace

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

                # Process TTS; _begin_output happened when the message was
                # queued, so always pair it here even when speech is skipped.
                try:
                    with self._lock:
                        if self._tts_engine and not self._tts_disabled:
                            try:
                                self.logger.info(f"Speaking: {message}")
                                self._tts_engine.say(message)
                                self._tts_engine.runAndWait()
                                self._tts_failures = 0  # Reset on success
                            except Exception as e:
                                self.logger.error(f"TTS error: {e}")
                                self._handle_tts_failure()
                finally:
                    self._end_output()

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
            self.logger.warning("TTS unavailable; message was not spoken")
            return False
        
        if not self._initialize_tts():
            self.logger.warning("TTS initialization failed; message was not spoken")
            return False
        
        try:
            self._tts_queue.put(message, timeout=1.0)
            # Count the message as pending output from queue time so a listen
            # cannot start in the gap before the worker begins speaking.
            self._begin_output()
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

        Returns True only on actual playback success. Returns False on missing
        backends, missing files, unknown types, or playback errors so that
        startup diagnostics report audio failures honestly.
        """
        if self._sound_disabled:
            self.logger.debug(f"Sound disabled (circuit breaker), skipping {sound_type}")
            return False
        if not SIMPLEAUDIO_AVAILABLE and not shutil.which("aplay"):
            self.logger.warning("No audio backend available (simpleaudio or aplay)")
            return False

        with self._sound_lock:
            audio_config = self._config.get_audio_config()
            sound_config = audio_config.get('feedback_sounds', {})

            sound_map = {
                'success': sound_config.get('success_sound', 'sounds/success.wav'),
                'error': sound_config.get('error_sound', 'sounds/error.wav'),
                'warning': sound_config.get(
                    'warning_sound',
                    sound_config.get('error_sound', 'sounds/error.wav'),
                ),
            }
            sound_file = sound_map.get(sound_type)
            if not sound_file:
                self.logger.warning(f"Unknown sound type: {sound_type}")
                return False

            if not os.path.isabs(sound_file):
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
                sound_file = os.path.join(project_root, 'assets', sound_file)

            if not os.path.exists(sound_file):
                self.logger.warning(f"Sound file not found: {sound_file}")
                return False

            self._begin_output()
            try:
                _play_wav_file(sound_file)
                self.logger.debug(f"Played {sound_type} sound: {sound_file}")
                self._sound_failures = 0
                return True
            except Exception as e:
                self.logger.error(f"Failed to play sound: {e}")
                self._handle_sound_failure()
                return False
            finally:
                self._end_output()
    
    def output_confirmation(self, message: str) -> bool:
        """Play the success chime, then speak the confirmation.

        The chime goes first: play_sound is synchronous while speak only
        queues to the TTS worker, so the reverse order had the chime firing
        over the start of the spoken message.

        Returns:
            True if output was successful.
        """
        success = self.play_sound('success')

        if message:
            success = self.speak(message) and success
        return success

    def output_error(self, message: str) -> bool:
        """Play the error chime, then speak the error message.

        Returns:
            True if output was successful.
        """
        success = self.play_sound('error')

        if message:
            success = self.speak(message) and success
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
            except Exception as e:
                self.logger.debug(f"Could not enqueue TTS shutdown sentinel: {e}")
        
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
