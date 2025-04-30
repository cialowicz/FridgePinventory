# Module for audio feedback

# Handle optional libraries
try:
    import pyttsx3
    tts_engine = pyttsx3.init()
    def output_confirmation(message: str = "") -> bool:
        """Output a confirmation message.
        
        Args:
            message (str): Optional message to include in the confirmation
            
        Returns:
            bool: True if confirmation was output successfully, False if message is empty
        """
        try:
            if not message:
                return False
            print(f"Confirmation: {message}")
            return True
        except Exception:
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