"""
Wake Word Detection Package
Supports multiple engines: Porcupine (Picovoice) and OpenWakeWord.
Engine selection is driven by WAKE_WORD_ENGINE in .env.
"""

from src.duck_config import WAKE_WORD_ENGINE, DUCK_NAME


def get_wait_for_wake_word():
    """Factory: returns the correct wait_for_wake_word function based on config."""
    if WAKE_WORD_ENGINE == 'openwakeword':
        from src.wake_word.openwakeword_engine import wait_for_wake_word
    else:
        from src.wake_word.porcupine_engine import wait_for_wake_word
    return wait_for_wake_word


def get_engine_name() -> str:
    """Return human-readable engine name for logging."""
    if WAKE_WORD_ENGINE == 'openwakeword':
        return f"OpenWakeWord ('{DUCK_NAME}')"
    else:
        return f"Porcupine ('{DUCK_NAME}')"
