# Module for audio feedback

import logging
import traceback

logger = logging.getLogger(__name__)

# Handle optional libraries
try:
    import pyttsx3
    engine = None

    def _initialize_tts_engine():
        global engine
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
                
                logger.info("TTS engine initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize pyttsx3 engine: {e}")
                logger.error(traceback.format_exc())
                engine = None # Ensure it's None if initialization failed
        return engine is not None

    def output_confirmation(message: str = "") -> bool:
        """Output a confirmation message using text-to-speech."""
        global engine
        logger.info(f"Attempting to speak: '{message}'")
        if not _initialize_tts_engine():
            logger.error("TTS engine not initialized. Cannot speak message.")
            return False

        if not message: # Don't try to speak an empty message
            logger.warning("output_confirmation called with an empty message.")
            return False
        
        try:
            engine.say(message)
            engine.runAndWait()
            logger.info("Successfully spoke message.")
            return True
        except Exception as e:
            logger.error(f"Error during pyttsx3 say() or runAndWait(): {e}")
            logger.error(traceback.format_exc())
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
        try:
            if success:
                playsound("sounds/success.wav")
            else:
                playsound("sounds/error.wav")
        except:
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