# Module for audio feedback

import logging
import os
import traceback
import threading
import queue
import time
from .config_manager import config

logger = logging.getLogger(__name__)

# Thread-safe TTS engine management
_tts_lock = threading.Lock()
_sound_lock = threading.Lock()
_tts_queue = queue.Queue()
_tts_thread = None
_shutdown_event = threading.Event()

# Handle optional libraries
try:
    import pyttsx3
    engine = None

    def _initialize_tts_engine():
        global engine
        with _tts_lock:
            if engine is None:
                logger.info("Initializing TTS engine (pyttsx3)...")
                try:
                    engine = pyttsx3.init()
                    # Optional: Log available voices and current voice properties
                    voices = engine.getProperty('voices')
                    if voices:
                        logger.debug(f"Found {len(voices)} voices.")
                        # for voice_idx, voice_obj in enumerate(voices):
                        #     logger.debug(f"  Voice {voice_idx}: ID: {voice_obj.id}, Name: {voice_obj.name}, Langs: {voice_obj.languages}, Gender: {voice_obj.gender}, Age: {voice_obj.age}")
                    current_voice_id = engine.getProperty('voice')
                    current_rate = engine.getProperty('rate')
                    current_volume = engine.getProperty('volume')
                    logger.debug(f"Current TTS Voice ID: {current_voice_id}, Rate: {current_rate}, Volume: {current_volume}")
                    
                    # You can set properties here if needed, e.g.:
                    # engine.setProperty('rate', 150)  # Adjust speed
                    # engine.setProperty('voice', 'english_rp+f3') # Example voice ID, find yours by listing
                    
                    # Apply configuration settings
                    audio_config = config.get_audio_config()
                    tts_config = audio_config.get('text_to_speech', {})
                    
                    rate = tts_config.get('rate', 150)
                    volume = tts_config.get('volume', 0.9)
                    voice_id = tts_config.get('voice_id')
                    
                    engine.setProperty('rate', rate)
                    engine.setProperty('volume', volume)
                    if voice_id:
                        engine.setProperty('voice', voice_id)
                        logger.info(f"Set TTS voice to: {voice_id}")
                    
                    logger.info(f"TTS engine initialized successfully with rate={rate}, volume={volume}")
                except Exception as e:
                    logger.error(f"Failed to initialize pyttsx3 engine: {e}")
                    logger.error(traceback.format_exc())
                    engine = None # Ensure it's None if initialization failed
        return engine is not None

    def _tts_worker():
        """Worker thread for TTS processing."""
        while not _shutdown_event.is_set():
            try:
                # Wait for message with timeout
                message = _tts_queue.get(timeout=1.0)
                if message is None:  # Shutdown signal
                    break
                    
                with _tts_lock:
                    if engine:
                        try:
                            engine.say(message)
                            engine.runAndWait()
                            logger.debug(f"TTS spoke: {message}")
                        except Exception as e:
                            logger.error(f"TTS error: {e}")
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS worker error: {e}")
    
    def _ensure_tts_thread():
        """Ensure TTS worker thread is running."""
        global _tts_thread
        if _tts_thread is None or not _tts_thread.is_alive():
            _tts_thread = threading.Thread(target=_tts_worker, daemon=True)
            _tts_thread.start()
            logger.debug("Started TTS worker thread")
    
    def output_confirmation(message: str = "") -> bool:
        """Output a confirmation message using text-to-speech."""
        logger.info(f"Attempting to speak: '{message}'")
        if not _initialize_tts_engine():
            logger.error("TTS engine not initialized. Cannot speak message.")
            return False

        if not message: # Don't try to speak an empty message
            logger.warning("output_confirmation called with an empty message.")
            return False
        
        try:
            _ensure_tts_thread()
            _tts_queue.put(message)
            logger.info("Message queued for TTS.")
            return True
        except Exception as e:
            logger.error(f"Error queueing TTS message: {e}")
            return False
except ImportError:
    def output_confirmation(message: str = "") -> bool:
        """Output a confirmation message using print."""
        if not message:
            return False
        print(f"Confirmation: {message}")
        return True

try:
    from playsound import playsound
    def play_feedback_sound(success):
        """Play an audio feedback sound if available, falls back to print."""
        with _sound_lock:
            try:
                # Get configured sound file paths
                audio_config = config.get_audio_config()
                sound_config = audio_config.get('feedback_sounds', {})
                
                # Get the project root directory (assuming this file is in src/pi_inventory_system/)
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.join(current_dir, '..', '..')
                project_root = os.path.abspath(project_root)
                
                if success:
                    sound_file = sound_config.get('success_sound', 'sounds/success.wav')
                    if not os.path.isabs(sound_file):
                        sound_file = os.path.join(project_root, 'assets', sound_file)
                    playsound(sound_file)
                    logger.info(f"Played success sound: {sound_file}")
                else:
                    sound_file = sound_config.get('error_sound', 'sounds/error.wav')
                    if not os.path.isabs(sound_file):
                        sound_file = os.path.join(project_root, 'assets', sound_file)
                    playsound(sound_file)
                    logger.info(f"Played error sound: {sound_file}")
            except Exception as e:
                logger.warning(f"Failed to play sound: {e}")
                print("Success" if success else "Error")
        return success
except ImportError:
    def play_feedback_sound(success):
        """Output feedback using print when audio is not available."""
        print("Success" if success else "Error")
        return success

def output_success(message: str = "") -> bool:
    """Output a success message.
    
    Args:
        message (str): Optional message to include in the success output
        
    Returns:
        bool: True if success was output successfully
    """
    try:
        if message:
            print(f"Success: {message}")
        else:
            print("Success")
        return True
    except Exception:
        return False

def output_failure(message: str = "") -> bool:
    """Output a failure message.
    
    Args:
        message (str): Optional message to include in the failure output
        
    Returns:
        bool: True if failure was output successfully
    """
    try:
        if message:
            print(f"Failure: {message}")
        else:
            print("Failure")
        return True
    except Exception:
        return False

def cleanup_audio_feedback():
    """Clean up audio feedback resources."""
    global engine, _tts_thread
    
    # Signal shutdown
    _shutdown_event.set()
    if _tts_queue:
        _tts_queue.put(None)  # Shutdown signal
    
    # Wait for thread to finish
    if _tts_thread and _tts_thread.is_alive():
        _tts_thread.join(timeout=2.0)
    
    # Clean up engine
    with _tts_lock:
        if engine:
            try:
                engine.stop()
                logger.info("TTS engine stopped")
            except Exception as e:
                logger.error(f"Error stopping TTS engine: {e}")
            engine = None
