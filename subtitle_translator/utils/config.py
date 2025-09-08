"""Configuration management for the subtitle translator."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration settings for the subtitle translator."""
    
    DEFAULT_CONFIG = {
        'translator': {
            'type': 'local_nllb',  # or 'huggingface'
            'endpoint': 'http://localhost:8080/translate',
            'api_key': '',
            'model_name': 'facebook/nllb-200-distilled-600M',
            'batch_size': 5,
            'timeout': 300,
        },
        'languages': {
            'source': 'eng_Latn',
            'target': 'nld_Latn',
            'available': {
                'eng_Latn': 'English',
                'nld_Latn': 'Dutch',
                'fra_Latn': 'French',
                'deu_Latn': 'German',
                'spa_Latn': 'Spanish',
                'ita_Latn': 'Italian',
                'por_Latn': 'Portuguese',
                'rus_Cyrl': 'Russian',
                'zho_Hans': 'Chinese (Simplified)',
                'jpn_Jpan': 'Japanese',
                'kor_Hang': 'Korean',
            }
        },
        'ui': {
            'theme': 'system',  # 'light', 'dark', or 'system'
            'font_size': 12,
            'recent_files': [],
            'window_geometry': None,
            'splitter_state': None,
        },
        'directories': {
            'last_used': str(Path.home() / 'Documents'),
            'save_location': str(Path.home() / 'Documents' / 'Translated Subtitles'),
        },
    }
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file. If None, uses default location.
        """
        if config_path is None:
            self.config_dir = Path.home() / '.config' / 'subtitle-translator'
            self.config_path = self.config_dir / 'config.json'
        else:
            self.config_path = Path(config_path)
            self.config_dir = self.config_path.parent
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create config
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default if not exists."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return self._merge_with_defaults(config)
        except Exception as e:
            logger.warning(f"Failed to load config from {self.config_path}: {e}")
        
        # Return default config if loading fails
        return self.DEFAULT_CONFIG.copy()
    
    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge a config dictionary with default values."""
        result = self.DEFAULT_CONFIG.copy()
        
        def merge(dest: Dict[str, Any], source: Dict[str, Any]) -> None:
            for key, value in source.items():
                if key in dest and isinstance(dest[key], dict) and isinstance(value, dict):
                    merge(dest[key], value)
                else:
                    dest[key] = value
        
        merge(result, config)
        return result
    
    def _convert_to_serializable(self, obj: Any) -> Any:
        """Convert non-serializable objects to a serializable format.
        
        Args:
            obj: Object to convert
            
        Returns:
            Serializable version of the object
        """
        if isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__'):  # Handle objects with __dict__
            return self._convert_to_serializable(obj.__dict__)
        elif hasattr(obj, 'toPyObject'):  # Handle QVariant
            return self._convert_to_serializable(obj.toPyObject())
        elif hasattr(obj, 'data'):  # Handle QByteArray and similar
            try:
                return bytes(obj).decode('utf-8', errors='replace')
            except:
                return str(obj)
        elif obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        else:
            return str(obj)
    
    def save(self) -> bool:
        """Save the current configuration to file.
        
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Create a serializable copy of the config
            serializable_config = self._convert_to_serializable(self._config)
            
            # Ensure the directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Write to a temporary file first
            temp_path = self.config_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_config, f, indent=2, ensure_ascii=False)
            
            # Replace the old config file atomically
            if self.config_path.exists():
                self.config_path.unlink()
            temp_path.rename(self.config_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_path}: {e}")
            if 'temp_path' in locals() and temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dot notation key.
        
        Args:
            key: Dot-notation key (e.g., 'translator.endpoint')
            default: Default value if key is not found
            
        Returns:
            The configuration value or default if not found
        """
        try:
            parts = key.split('.')
            value = self._config
            for part in parts:
                value = value[part]
            return value
        except (KeyError, AttributeError, TypeError):
            return default
    
    def set(self, key: str, value: Any, save: bool = True) -> bool:
        """Set a configuration value by dot notation key.
        
        Args:
            key: Dot-notation key (e.g., 'translator.endpoint')
            value: Value to set
            save: Whether to save the configuration after updating
            
        Returns:
            bool: True if the update was successful, False otherwise
        """
        try:
            parts = key.split('.')
            current = self._config
            
            # Navigate to the parent of the target key
            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]
            
            # Set the value
            current[parts[-1]] = value
            
            # Save if requested
            if save:
                return self.save()
            return True
            
        except Exception as e:
            logger.error(f"Failed to set config key {key}: {e}")
            return False
    
    def update(self, updates: Dict[str, Any], save: bool = True) -> bool:
        """Update multiple configuration values at once.
        
        Args:
            updates: Dictionary of key-value pairs to update
            save: Whether to save the configuration after updating
            
        Returns:
            bool: True if all updates were successful, False otherwise
        """
        success = True
        for key, value in updates.items():
            if not self.set(key, value, save=False):
                success = False
        
        if save and success:
            return self.save()
        return success
    
    def get_available_languages(self) -> Dict[str, str]:
        """Get the available languages for translation.
        
        Returns:
            Dictionary mapping language codes to display names
        """
        return self.get('languages.available', {})
    
    def add_recent_file(self, file_path: Union[str, Path]) -> None:
        """Add a file to the list of recently used files.
        
        Args:
            file_path: Path to the file to add
        """
        recent_files = self.get('ui.recent_files', [])
        file_path = str(Path(file_path).resolve())
        
        # Remove if already exists
        if file_path in recent_files:
            recent_files.remove(file_path)
        
        # Add to the beginning
        recent_files.insert(0, file_path)
        
        # Keep only the 10 most recent
        recent_files = recent_files[:10]
        
        self.set('ui.recent_files', recent_files)
    
    def get_recent_files(self) -> List[str]:
        """Get the list of recently used files.
        
        Returns:
            List of file paths
        """
        return self.get('ui.recent_files', [])
    
    def clear_recent_files(self) -> None:
        """Clear the list of recently used files."""
        self.set('ui.recent_files', [])
