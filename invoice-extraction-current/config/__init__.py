"""
Configuration Module for Invoice Extraction System.

This module provides centralized configuration management using YAML files.
All system parameters should be controlled through configuration, not hard-coded.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigurationManager:
    """
    Centralized configuration management for the invoice extraction system.
    
    This class handles loading, validating, and providing access to all
    configuration parameters defined in settings.yaml.
    
    Attributes:
        config_path (Path): Path to the configuration file.
        config (Dict): Loaded configuration dictionary.
    
    Example:
        >>> config = ConfigurationManager()
        >>> ocr_engine = config.get("ocr.engine")
        >>> model_name = config.get("model.name")
    """
    
    _instance: Optional['ConfigurationManager'] = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls, config_path: Optional[str] = None) -> 'ConfigurationManager':
        """
        Singleton pattern to ensure only one configuration instance exists.
        
        Args:
            config_path: Optional path to configuration file.
            
        Returns:
            ConfigurationManager instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Optional path to configuration file.
                        Defaults to config/settings.yaml.
        """
        if self._initialized:
            return
            
        # Determine configuration file path
        if config_path is None:
            # Default to settings.yaml in the config directory
            self.config_path = Path(__file__).parent / "settings.yaml"
        else:
            self.config_path = Path(config_path)
        
        # Load configuration
        self._load_config()
        self._initialized = True
    
    def _load_config(self) -> None:
        """
        Load configuration from YAML file.
        
        Raises:
            FileNotFoundError: If configuration file doesn't exist.
            yaml.YAMLError: If configuration file is invalid.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            )
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        # Resolve relative paths to absolute paths
        self._resolve_paths()
    
    def _resolve_paths(self) -> None:
        """
        Resolve relative paths in configuration to absolute paths.
        Uses project root as base directory.
        """
        project_root = Path(__file__).parent.parent
        
        if 'paths' in self._config:
            for key, value in self._config['paths'].items():
                if value and not Path(value).is_absolute():
                    self._config['paths'][key] = str(project_root / value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key: Configuration key in dot notation (e.g., "ocr.engine").
            default: Default value if key doesn't exist.
            
        Returns:
            Configuration value or default.
            
        Example:
            >>> config.get("model.name")
            "microsoft/layoutlmv3-base"
            >>> config.get("nonexistent.key", "default_value")
            "default_value"
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get the complete configuration dictionary.
        
        Returns:
            Complete configuration dictionary.
        """
        return self._config.copy()
    
    def reload(self) -> None:
        """
        Reload configuration from file.
        Useful for dynamic configuration updates.
        """
        self._load_config()
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton instance.
        Useful for testing or configuration changes.
        """
        cls._instance = None


# Convenience function for quick access
def get_config(key: str, default: Any = None) -> Any:
    """
    Convenience function to get configuration values.
    
    Args:
        key: Configuration key in dot notation.
        default: Default value if key doesn't exist.
        
    Returns:
        Configuration value or default.
    """
    return ConfigurationManager().get(key, default)


# Export public API
__all__ = ['ConfigurationManager', 'get_config']
