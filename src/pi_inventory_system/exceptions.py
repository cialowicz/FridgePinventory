# Custom exception classes for the FridgePinventory system

class FridgePinventoryError(Exception):
    """Base exception class for FridgePinventory system."""
    pass


class DatabaseError(FridgePinventoryError):
    """Raised when database operations fail."""
    pass


class ConfigurationError(FridgePinventoryError):
    """Raised when configuration is invalid or missing."""
    pass


class DisplayError(FridgePinventoryError):
    """Raised when display operations fail."""
    pass


class AudioError(FridgePinventoryError):
    """Raised when audio operations fail."""
    pass


class VoiceRecognitionError(AudioError):
    """Raised when voice recognition fails."""
    pass


class TextToSpeechError(AudioError):
    """Raised when text-to-speech fails."""
    pass


class CommandProcessingError(FridgePinventoryError):
    """Raised when command processing fails."""
    pass


class InventoryError(FridgePinventoryError):
    """Raised when inventory operations fail."""
    pass


class HardwareError(FridgePinventoryError):
    """Raised when hardware initialization or operation fails."""
    pass


class MotionSensorError(HardwareError):
    """Raised when motion sensor operations fail."""
    pass
