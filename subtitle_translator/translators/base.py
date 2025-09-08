"""Base translator interface for the subtitle translator."""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Union

class BaseTranslator(ABC):
    """Abstract base class for all translator implementations."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the translator with the given configuration.
        
        Args:
            config: Configuration dictionary for the translator
        """
        self.config = config or {}
    
    @abstractmethod
    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        **kwargs
    ) -> str:
        """Translate a single text string.
        
        Args:
            text: The text to translate
            source_language: Source language code (e.g., 'eng_Latn')
            target_language: Target language code (e.g., 'nld_Latn')
            **kwargs: Additional translator-specific parameters
            
        Returns:
            The translated text
        """
        pass
    
    @abstractmethod
    async def translate_file(
        self,
        input_file: Union[str, Path],
        output_file: Union[str, Path],
        source_language: str,
        target_language: str,
        **kwargs
    ) -> bool:
        """Translate a subtitle file.
        
        Args:
            input_file: Path to the input subtitle file
            output_file: Path to save the translated file
            source_language: Source language code (e.g., 'eng_Latn')
            target_language: Target language code (e.g., 'nld_Latn')
            **kwargs: Additional translator-specific parameters
            
        Returns:
            bool: True if translation was successful, False otherwise
        """
        pass
    
    async def close(self):
        """Close any resources used by the translator."""
        pass
    
    def __del__(self):
        """Ensure resources are cleaned up when the object is destroyed."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If there's a running event loop, create a task to close the translator
                loop.create_task(self.close())
            else:
                # If no running event loop, run the coroutine in a new event loop
                loop.run_until_complete(self.close())
        except Exception as e:
            # Log any errors during cleanup but don't raise
            import logging
            logging.getLogger(__name__).warning(f"Error during translator cleanup: {e}")
        except:
            # Ensure we don't raise exceptions during cleanup
            pass
