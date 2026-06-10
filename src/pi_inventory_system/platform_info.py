"""Platform detection helpers shared across managers."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL_FILE = "/proc/device-tree/model"
DEFAULT_PI_STRING = "raspberry pi"
DEFAULT_PI5_STRING = "raspberry pi 5"


def _read_model(model_file: str = DEFAULT_MODEL_FILE) -> Optional[str]:
    if not os.path.exists(model_file):
        return None
    try:
        with open(model_file, "r") as f:
            return f.read().lower()
    except OSError as e:
        logger.warning(f"Could not read platform model file {model_file}: {e}")
        return None


def is_raspberry_pi(model_file: str = DEFAULT_MODEL_FILE,
                    required_string: str = DEFAULT_PI_STRING) -> bool:
    model = _read_model(model_file)
    return model is not None and required_string in model


def is_raspberry_pi_5(model_file: str = DEFAULT_MODEL_FILE) -> bool:
    model = _read_model(model_file)
    return model is not None and DEFAULT_PI5_STRING in model
