# Configuration management module

import os
import yaml
import logging
from typing import Any, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """Singleton configuration manager for the FridgePinventory system."""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self.load_config()
    
    def load_config(self, config_path: Optional[str] = None) -> None:
        """Load configuration from YAML file with environment variable overrides."""
        if config_path is None:
            # Look for config file in project root
            current_dir = Path(__file__).parent
            project_root = current_dir.parent.parent
            config_path = project_root / "config.yaml"
        
        try:
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
        except FileNotFoundError:
            logger.warning(f"Config file not found at {config_path}, using defaults")
            self._config = self._get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing config file: {e}")
            self._config = self._get_default_config()
        
        # Apply environment variable overrides
        self._apply_env_overrides()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration values."""
        return {
            'database': {
                'path': ':memory:'
            },
            'display': {
                'font': {
                    'path': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                    'size': 16,
                    'fallback_size': 12
                },
                'layout': {
                    'items_per_row': 2,
                    'lozenge_width_margin': 30,
                    'lozenge_height': 40,
                    'spacing': 10,
                    'margin': 10
                },
                'colors': {
                    'background': 'white',
                    'text': 'black',
                    'border_normal': 'black',
                    'border_low_stock': 'yellow',
                    'low_stock_threshold': 2
                }
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
                    'error_sound': 'sounds/error.wav'
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
                'log_level': 'INFO',
                'enable_diagnostics': True
            },
            'hardware': {
                'motion_sensor': {
                    'enabled': True,
                    'pin': None
                },
                'display': {
                    'enabled': True,
                    'auto_detect': True,
                    'type': None,
                    'color': None
                }
            }
        }
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        env_mappings = {
            'FRIDGEP_DB_PATH': ['database', 'path'],
            'FRIDGEP_LOG_LEVEL': ['system', 'log_level'],
            'FRIDGEP_FONT_PATH': ['display', 'font', 'path'],
            'FRIDGEP_FONT_SIZE': ['display', 'font', 'size'],
            'FRIDGEP_AUDIO_TIMEOUT': ['audio', 'voice_recognition', 'timeout'],
            'FRIDGEP_SIMILARITY_THRESHOLD': ['commands', 'similarity_threshold'],
            'FRIDGEP_MAIN_LOOP_DELAY': ['system', 'main_loop_delay'],
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Convert string values to appropriate types
                if config_path[-1] in ['size', 'timeout', 'pin']:
                    try:
                        env_value = int(env_value)
                    except ValueError:
                        logger.warning(f"Invalid integer value for {env_var}: {env_value}")
                        continue
                elif config_path[-1] in ['similarity_threshold', 'volume', 'main_loop_delay']:
                    try:
                        env_value = float(env_value)
                    except ValueError:
                        logger.warning(f"Invalid float value for {env_var}: {env_value}")
                        continue
                elif config_path[-1] in ['enabled', 'auto_detect', 'enable_diagnostics']:
                    env_value = env_value.lower() in ('true', '1', 'yes', 'on')
                
                # Set the value in config
                current = self._config
                for key in config_path[:-1]:
                    current = current.setdefault(key, {})
                current[config_path[-1]] = env_value
                logger.info(f"Applied environment override: {env_var} = {env_value}")
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation.
        
        Args:
            *keys: Configuration keys (e.g., 'database', 'path')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
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
    
    def reload_config(self, config_path: Optional[str] = None) -> None:
        """Reload configuration from file."""
        self._config = None
        self.load_config(config_path)


# Global configuration instance
config = ConfigManager()
