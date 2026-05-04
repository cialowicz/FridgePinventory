# Configuration management module

import logging
import os
from copy import deepcopy
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .constants import ACTIVATION_AUTO, VALID_ACTIVATION_MODES
from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: Dict[str, Any] = {
    'database': {
        'path': '~/.local/share/fridgepinventory/inventory.db'
    },
    'display': {
        'font': {
            'path': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            'size': 16,
            'fallback_size': 12
        },
        'layout': {
            'items_per_row': 4,
            'lozenge_height': 60,
            'spacing': 15,
            'margin': 20
        },
        'colors': {
            'background': 'white',
            'text': 'black',
            'border_normal': 'black',
            'border_low_stock': 'yellow',
            'low_stock_threshold': 2
        },
        'clear_on_shutdown': False,
        'max_stale_seconds': 300.0,
        'show_startup_message': False,
    },
    'audio': {
        'voice_recognition': {
            'timeout': 5,
            'phrase_time_limit': 10,
            'engine': 'sphinx',
            'device_index': None
        },
        'text_to_speech': {
            'rate': 150,
            'volume': 0.9,
            'voice_id': None
        },
        'feedback_sounds': {
            'success_sound': 'sounds/success.wav',
            'error_sound': 'sounds/error.wav',
            'warning_sound': 'sounds/error.wav'
        }
    },
    'commands': {
        'similarity_threshold': 0.8,
        'special_quantities': {
            'a': 1,
            'an': 1,
            'few': 3,
            'several': 3
        }
    },
    'system': {
        'main_loop_delay': 0.1,
        'motion_check_interval': 0.5,
        'idle_delay': 1.0,
        'log_level': 'INFO',
        'enable_diagnostics': True,
        'activation_mode': ACTIVATION_AUTO,
        'simulation_voice_interval': 5.0,
    },
    'hardware': {
        'motion_sensor': {
            'enabled': True,
            'pin': 4
        },
        'display': {
            'enabled': True,
            'auto_detect': True,
            'type': 'Waveshare_397',
            'resolution': '800x480',
            'grayscale_levels': 4
        }
    },
    'nlp': {
        'spacy_model': 'en_core_web_sm',
        'enable_spacy': True
    },
    'database_advanced': {
        'timeout': 30.0,
        'wal_mode': 'WAL',
        'cache_size': 1000,
        'synchronous_mode': 'NORMAL',
        'temp_store': 'memory'
    },
    'platform': {
        'raspberry_pi_model_file': '/proc/device-tree/model',
        'required_pi_string': 'raspberry pi'
    }
}


class ConfigManager:
    """Thread-safe configuration manager for the FridgePinventory system."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file. If None, uses default location.
        """
        self._config: Optional[Dict[str, Any]] = None
        self._config_path = config_path
        self._lock = threading.RLock()
        self.load_config(config_path)
    
    def load_config(self, config_path: Optional[str] = None) -> None:
        """Load configuration from YAML file with environment variable overrides."""
        if config_path is None:
            # Look for config file in project root
            current_dir = Path(__file__).parent
            project_root = current_dir.parent.parent
            config_path = project_root / "config.yaml"
        
        with self._lock:
            try:
                with open(config_path, 'r') as f:
                    loaded = yaml.safe_load(f)
                if loaded is None:
                    loaded = {}
                if not isinstance(loaded, dict):
                    raise ConfigurationError("Config file must contain a YAML mapping")
                self._config = self._merge_config(self._get_default_config(), loaded)
                logger.info(f"Configuration loaded from {config_path}")
            except FileNotFoundError:
                logger.warning(f"Config file not found at {config_path}, using defaults")
                self._config = self._get_default_config()
            except yaml.YAMLError as e:
                logger.error(f"Error parsing config file: {e}")
                raise ConfigurationError(f"Invalid YAML in {config_path}: {e}") from e

            self._apply_env_overrides()
            self._validate_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration values."""
        return deepcopy(DEFAULT_CONFIG)

    def _merge_config(self, defaults: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Deep-merge user config over defaults."""
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(defaults.get(key), dict):
                defaults[key] = self._merge_config(defaults[key], value)
            else:
                defaults[key] = value
        return defaults

    def _validate_config(self) -> None:
        system = self.get_system_config()
        activation_mode = str(system.get('activation_mode', ACTIVATION_AUTO)).lower()
        if activation_mode not in VALID_ACTIVATION_MODES:
            raise ConfigurationError(
                f"Invalid system.activation_mode '{activation_mode}'. "
                f"Expected one of: {', '.join(sorted(VALID_ACTIVATION_MODES))}"
            )
    
    def _convert_env_value(self, key: str, value: str) -> Any:
        """Convert environment variable string to appropriate type."""
        if key in ['size', 'fallback_size', 'items_per_row', 'lozenge_height', 'spacing',
                   'margin', 'low_stock_threshold', 'timeout', 'phrase_time_limit', 'rate',
                   'device_index', 'pin', 'grayscale_levels', 'cache_size']:
            try:
                return int(value)
            except ValueError:
                logger.warning(f"Invalid integer value for {key}: {value}")
                return None
        elif key in ['similarity_threshold', 'volume', 'main_loop_delay',
                     'motion_check_interval', 'idle_delay', 'max_stale_seconds',
                     'simulation_voice_interval']:
            try:
                return float(value)
            except ValueError:
                logger.warning(f"Invalid float value for {key}: {value}")
                return None
        elif key in ['enabled', 'auto_detect', 'enable_diagnostics', 'enable_spacy',
                     'clear_on_shutdown', 'show_startup_message']:
            return value.lower() in ('true', '1', 'yes', 'on')
        return value

    def _apply_env_overrides(self):
        """Apply environment variable overrides to configuration."""
        for env_var, env_value in os.environ.items():
            if env_var.startswith("FRIDGE_"):
                config_path = env_var[7:].lower().split('__')
                
                converted_value = self._convert_env_value(config_path[-1], env_value)
                if converted_value is None:
                    continue
                
                current = self._config
                for key in config_path[:-1]:
                    current = current.setdefault(key, {})
                current[config_path[-1]] = converted_value
                logger.info(f"Applied environment override: {env_var} = {converted_value}")

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation.
        
        Args:
            *keys: Configuration keys (e.g., 'database', 'path')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        with self._lock:
            current = self._config
            try:
                for key in keys:
                    current = current[key]
                return current
            except (KeyError, TypeError):
                return default
    
    def get_database_path(self) -> str:
        """Get database path."""
        return self.get('database', 'path', default=':memory:')
    
    def get_font_config(self) -> Dict[str, Any]:
        """Get font configuration."""
        return self.get('display', 'font', default={})
    
    def get_layout_config(self) -> Dict[str, Any]:
        """Get display layout configuration."""
        return self.get('display', 'layout', default={})
    
    def get_audio_config(self) -> Dict[str, Any]:
        """Get audio configuration."""
        return self.get('audio', default={})
    
    def get_command_config(self) -> Dict[str, Any]:
        """Get command processing configuration."""
        return self.get('commands', default={})
    
    def get_system_config(self) -> Dict[str, Any]:
        """Get system configuration."""
        return self.get('system', default={})
    
    def get_hardware_config(self) -> Dict[str, Any]:
        """Get hardware configuration."""
        return self.get('hardware', default={})
    
    def get_nlp_config(self) -> Dict[str, Any]:
        """Get NLP configuration."""
        return self.get('nlp', default={})
    
    def get_database_advanced_config(self) -> Dict[str, Any]:
        """Get advanced database configuration."""
        return self.get('database_advanced', default={})
    
    def get_platform_config(self) -> Dict[str, Any]:
        """Get platform configuration."""
        return self.get('platform', default={})
    
    def reload_config(self, config_path: Optional[str] = None) -> None:
        """Reload configuration from file."""
        with self._lock:
            self._config = None
        self.load_config(config_path)


# Factory function to create configuration manager instances
def create_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """Create a new configuration manager instance.
    
    Args:
        config_path: Path to the configuration file. If None, uses default location.
        
    Returns:
        ConfigManager instance
    """
    return ConfigManager(config_path)


_default_config_manager: Optional[ConfigManager] = None
_default_config_lock = threading.Lock()


def get_default_config_manager() -> ConfigManager:
    """Lazily create and return a process-wide default ConfigManager."""
    global _default_config_manager
    with _default_config_lock:
        if _default_config_manager is None:
            _default_config_manager = create_config_manager()
        return _default_config_manager
