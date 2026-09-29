"""
Configuration Management Module (read-only)

Provides read-only access to the Home Assistant configuration:
- Path validation with traversal protection
- Raw file reading
- File listing for the documentation agent

The parent project's write machinery (atomic writes, backups, validation)
has been removed together with the ValidationError it raised.
"""
from .manager import (
    ConfigurationManager,
    ConfigurationError
)

__all__ = [
    'ConfigurationManager',
    'ConfigurationError'
]