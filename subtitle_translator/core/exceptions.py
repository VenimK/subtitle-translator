"""Custom exceptions for the subtitle translator."""

class TranslationError(Exception):
    """Base exception for translation errors."""
    pass

class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass

class FileError(Exception):
    """Exception raised for file-related errors."""
    pass

class ValidationError(Exception):
    """Exception raised for validation errors."""
    pass
