"""
Logging Configuration Module.

This module provides centralized logging configuration for the entire
invoice extraction system. It supports both file and console logging
with configurable levels and formats.

Usage:
    from src.utils.logger import setup_logger, get_logger
    
    # Initialize logging (call once at startup)
    setup_logger()
    
    # Get logger in any module
    logger = get_logger(__name__)
    logger.info("Processing invoice...")
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

# Try to import colorama for colored console output
try:
    import colorama
    from colorama import Fore, Style
    colorama.init()
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds color to console log output.
    
    Colors:
        - DEBUG: Cyan
        - INFO: Green
        - WARNING: Yellow
        - ERROR: Red
        - CRITICAL: Red (bold)
    """
    
    COLORS = {
        logging.DEBUG: Fore.CYAN if COLORAMA_AVAILABLE else '',
        logging.INFO: Fore.GREEN if COLORAMA_AVAILABLE else '',
        logging.WARNING: Fore.YELLOW if COLORAMA_AVAILABLE else '',
        logging.ERROR: Fore.RED if COLORAMA_AVAILABLE else '',
        logging.CRITICAL: Fore.RED + Style.BRIGHT if COLORAMA_AVAILABLE else '',
    }
    RESET = Style.RESET_ALL if COLORAMA_AVAILABLE else ''
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with color codes.
        
        Args:
            record: Log record to format.
            
        Returns:
            Formatted log string with color codes.
        """
        color = self.COLORS.get(record.levelno, '')
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


def setup_logger(
    level: str = "INFO",
    log_format: Optional[str] = None,
    date_format: Optional[str] = None,
    log_file: Optional[str] = None,
    max_bytes: int = 10485760,  # 10 MB
    backup_count: int = 5,
    colorize: bool = True
) -> logging.Logger:
    """
    Configure the root logger for the invoice extraction system.
    
    This function should be called once at application startup to
    initialize logging. All subsequent calls to get_logger() will
    inherit this configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Custom log format string.
        date_format: Custom date format string.
        log_file: Path to log file. If None, file logging is disabled.
        max_bytes: Maximum log file size before rotation.
        backup_count: Number of backup files to keep.
        colorize: Whether to colorize console output.
        
    Returns:
        Configured root logger.
        
    Example:
        >>> setup_logger(level="DEBUG", log_file="logs/app.log")
    """
    # Default formats
    if log_format is None:
        log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    if date_format is None:
        date_format = "%Y-%m-%d %H:%M:%S"
    
    # Get root logger for our application
    root_logger = logging.getLogger("invoice_extraction")
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    if colorize and COLORAMA_AVAILABLE:
        console_formatter = ColoredFormatter(log_format, datefmt=date_format)
    else:
        console_formatter = logging.Formatter(log_format, datefmt=date_format)
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if log file specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    root_logger.propagate = False
    
    root_logger.info("Logging initialized successfully")
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Name for the logger, typically __name__.
        
    Returns:
        Logger instance.
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    # Create child logger under our application namespace
    if name.startswith("invoice_extraction"):
        return logging.getLogger(name)
    return logging.getLogger(f"invoice_extraction.{name}")


# Convenience function to initialize logging from config
def setup_logger_from_config() -> logging.Logger:
    """
    Initialize logging using settings from configuration file.
    
    Returns:
        Configured root logger.
    """
    try:
        from config import get_config
        
        level = get_config("logging.level", "INFO")
        log_format = get_config("logging.format")
        date_format = get_config("logging.date_format")
        
        log_file = None
        if get_config("logging.file.enabled", False):
            log_file = get_config("logging.file.path")
        
        max_bytes = get_config("logging.file.max_bytes", 10485760)
        backup_count = get_config("logging.file.backup_count", 5)
        colorize = get_config("logging.console.colorize", True)
        
        return setup_logger(
            level=level,
            log_format=log_format,
            date_format=date_format,
            log_file=log_file,
            max_bytes=max_bytes,
            backup_count=backup_count,
            colorize=colorize
        )
    except Exception as e:
        # Fallback to default configuration
        print(f"Warning: Could not load logging config, using defaults: {e}")
        return setup_logger()
