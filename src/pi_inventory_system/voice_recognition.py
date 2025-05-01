# Module for handling voice commands

import speech_recognition as sr
from speech_recognition.exceptions import UnknownValueError, RequestError


def recognize_speech_from_mic():
    """Capture speech from the microphone and return the recognized text."""
    try:
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()

        with microphone as source:
            print("Listening...")
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source)

        try:
            print("Recognizing...")
            # Use Google's speech recognition
            text = recognizer.recognize_google(audio)
            print(f"Recognized: {text}")
            return text
        except UnknownValueError:
            print("Could not understand audio")
            return None
        except RequestError:
            print("Could not request results")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None
    except Exception as e:
        print(f"Error initializing microphone: {e}")
        return None
