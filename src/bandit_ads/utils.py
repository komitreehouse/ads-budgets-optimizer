"""
Utility functions for error handling, logging, and configuration management.
"""

import logging
import os
import json
from pathlib import Path
from functools import wraps
from typing import Optional, Dict, Any
import time

# Optional YAML support
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Configure logging
def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """
    Set up logging configuration for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    logger = logging.getLogger('bandit_ads')
    logger.setLevel(level)
    logger.handlers.clear()  # Remove existing handlers
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module."""
    return logging.getLogger(f'bandit_ads.{name}')

# Error handling decorators
def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry a function on failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay on each retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                            f"Retrying in {wait_time:.2f}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {str(e)}")
            
            raise last_exception
        return wrapper
    return decorator

def handle_errors(default_return=None, log_error: bool = True):
    """
    Decorator to handle errors gracefully.
    
    Args:
        default_return: Value to return on error
        log_error: Whether to log the error
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger = get_logger(func.__module__)
                    logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                return default_return
        return wrapper
    return decorator

# Configuration management
class ConfigManager:
    """Manages application configuration from files and environment variables."""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to YAML or JSON config file
        """
        self.config: Dict[str, Any] = {}
        self.logger = get_logger('config')
        
        # Load from file if provided
        if config_file:
            self.load_from_file(config_file)
        
        # Override with environment variables
        self.load_from_env()
    
    def load_from_file(self, filepath: str):
        """Load configuration from YAML or JSON file."""
        path = Path(filepath)
        
        if not path.exists():
            self.logger.warning(f"Config file not found: {filepath}")
            return
        
        try:
            with open(path, 'r') as f:
                if path.suffix in ['.yaml', '.yml']:
                    if not YAML_AVAILABLE:
                        self.logger.error(
                            "YAML support not available. Install with: pip install pyyaml"
                        )
                        return
                    self.config.update(yaml.safe_load(f) or {})
                elif path.suffix == '.json':
                    self.config.update(json.load(f))
                else:
                    self.logger.error(f"Unsupported config file format: {path.suffix}")
        except Exception as e:
            self.logger.error(f"Error loading config file {filepath}: {str(e)}")
    
    def load_from_env(self):
        """Load configuration from environment variables."""
        # Common environment variables
        env_mappings = {
            'BANDIT_ADS_LOG_LEVEL': 'logging.level',
            'BANDIT_ADS_LOG_FILE': 'logging.file',
            'BANDIT_ADS_BUDGET': 'agent.total_budget',
            'GOOGLE_ADS_CLIENT_ID': 'api.google.client_id',
            'GOOGLE_ADS_CLIENT_SECRET': 'api.google.client_secret',
            'GOOGLE_ADS_REFRESH_TOKEN': 'api.google.refresh_token',
            'META_ACCESS_TOKEN': 'api.meta.access_token',
            'META_APP_ID': 'api.meta.app_id',
            'META_APP_SECRET': 'api.meta.app_secret',
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                self._set_nested_config(config_path, value)
    
    def _set_nested_config(self, path: str, value: Any):
        """Set a nested configuration value using dot notation."""
        keys = path.split('.')
        current = self.config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Convert numeric strings to appropriate types
        if isinstance(value, str):
            if value.isdigit():
                value = int(value)
            elif value.replace('.', '', 1).isdigit():
                value = float(value)
            elif value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
        
        current[keys[-1]] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'agent.total_budget')
            default: Default value if key not found
        """
        keys = key.split('.')
        current = self.config
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
    
    def set(self, key: str, value: Any):
        """Set configuration value using dot notation."""
        self._set_nested_config(key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self.config.copy()

# Input validation
def validate_positive_number(value: Any, name: str) -> float:
    """Validate that a value is a positive number."""
    try:
        num = float(value)
        if num < 0:
            raise ValueError(f"{name} must be non-negative, got {num}")
        return num
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")

def validate_probability(value: Any, name: str) -> float:
    """Validate that a value is a probability (0-1)."""
    num = validate_positive_number(value, name)
    if num > 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {num}")
    return num

def validate_arm_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate arm-specific parameters."""
    validated = {}
    
    if 'ctr' in params:
        validated['ctr'] = validate_probability(params['ctr'], 'CTR')
    if 'cvr' in params:
        validated['cvr'] = validate_probability(params['cvr'], 'CVR')
    if 'revenue' in params:
        validated['revenue'] = validate_positive_number(params['revenue'], 'Revenue')
    if 'cpc' in params:
        validated['cpc'] = validate_positive_number(params['cpc'], 'CPC')
    
    return validated
