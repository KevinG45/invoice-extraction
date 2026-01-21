"""
Helper Utilities Module.

This module provides common utility functions used throughout the
invoice extraction system. Functions here should be generic and
reusable across different modules.

Functions:
    - ensure_directory: Create directory if it doesn't exist
    - get_file_extension: Extract file extension safely
    - generate_timestamp: Generate formatted timestamps
    - safe_filename: Sanitize filenames for filesystem
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Union, Optional


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    This function creates the directory and all parent directories
    if they don't already exist. It's safe to call even if the
    directory already exists.
    
    Args:
        path: Directory path to ensure exists.
        
    Returns:
        Path object pointing to the directory.
        
    Raises:
        PermissionError: If directory cannot be created due to permissions.
        
    Example:
        >>> ensure_directory("outputs/reports")
        PosixPath('outputs/reports')
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_file_extension(filepath: Union[str, Path]) -> str:
    """
    Extract the file extension from a filepath.
    
    Returns the extension in lowercase, including the dot.
    Returns empty string if no extension exists.
    
    Args:
        filepath: Path to the file.
        
    Returns:
        Lowercase file extension including dot (e.g., ".pdf").
        
    Example:
        >>> get_file_extension("document.PDF")
        ".pdf"
        >>> get_file_extension("noextension")
        ""
    """
    return Path(filepath).suffix.lower()


def generate_timestamp(format_str: str = "%Y%m%d_%H%M%S") -> str:
    """
    Generate a formatted timestamp string.
    
    Args:
        format_str: strftime format string.
        
    Returns:
        Formatted timestamp string.
        
    Example:
        >>> generate_timestamp()
        "20260121_143022"
        >>> generate_timestamp("%Y-%m-%d")
        "2026-01-21"
    """
    return datetime.now().strftime(format_str)


def safe_filename(filename: str, replacement: str = "_") -> str:
    """
    Sanitize a filename by removing or replacing invalid characters.
    
    Removes characters that are not allowed in filenames on Windows
    and other operating systems.
    
    Args:
        filename: Original filename.
        replacement: Character to replace invalid characters with.
        
    Returns:
        Sanitized filename safe for filesystem.
        
    Example:
        >>> safe_filename("invoice:123/test.pdf")
        "invoice_123_test.pdf"
    """
    # Characters not allowed in Windows filenames
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, replacement, filename)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')
    
    # Ensure filename is not empty
    if not sanitized:
        sanitized = "unnamed"
    
    return sanitized


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: File size in bytes.
        
    Returns:
        Human-readable file size string.
        
    Example:
        >>> format_file_size(1536)
        "1.5 KB"
        >>> format_file_size(1048576)
        "1.0 MB"
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def validate_file_exists(filepath: Union[str, Path]) -> bool:
    """
    Check if a file exists and is a regular file.
    
    Args:
        filepath: Path to check.
        
    Returns:
        True if file exists and is a regular file.
        
    Example:
        >>> validate_file_exists("config/settings.yaml")
        True
    """
    path = Path(filepath)
    return path.exists() and path.is_file()


def get_project_root() -> Path:
    """
    Get the project root directory.
    
    Traverses up from the current file location to find the project root,
    identified by the presence of key files/directories.
    
    Returns:
        Path to project root directory.
    """
    # Start from this file's directory and go up
    current = Path(__file__).resolve()
    
    # Go up to src, then to project root
    for parent in current.parents:
        if (parent / "config").exists() and (parent / "src").exists():
            return parent
    
    # Fallback to two levels up from this file
    return current.parent.parent.parent


def merge_dicts(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries, with override taking precedence.
    
    Args:
        base: Base dictionary.
        override: Dictionary with values to override.
        
    Returns:
        Merged dictionary.
        
    Example:
        >>> base = {"a": 1, "b": {"c": 2}}
        >>> override = {"b": {"d": 3}}
        >>> merge_dicts(base, override)
        {"a": 1, "b": {"c": 2, "d": 3}}
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result
