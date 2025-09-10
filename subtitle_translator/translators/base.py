"""Base translator interface for the subtitle translator."""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Tuple
import logging
import pysubs2
import warnings

logger = logging.getLogger(__name__)

class BaseTranslator(ABC):
    """Abstract base class for all translator implementations."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the translator with the given configuration.

        Args:
            config: Configuration dictionary for the translator
        """
        self.config = config or {}
        self.batch_size = int(self.config.get('batch_size', 5))

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

    async def translate_file(
        self,
        input_file: Union[str, Path],
        source_language: str,
        target_language: str,
        **kwargs
    ) -> Optional[Tuple[pysubs2.SSAFile, pysubs2.SSAFile]]:
        """Translate a subtitle file and return original and translated subs objects."""
        input_path = Path(input_file)

        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                original_subs = pysubs2.load(str(input_path), encoding="utf-8")
                translated_subs = pysubs2.load(str(input_path), encoding="utf-8") # Create a copy for translation
        except Exception as e:
            logger.error(f"Failed to read or parse subtitle file {input_path}: {e}")
            return None

        text_blocks = [event.plaintext for event in original_subs]

        if not text_blocks:
            logger.warning(f"No translatable text found in {input_path}")
            return original_subs, translated_subs

        try:
            translated_blocks = await self._translate_batch(
                text_blocks,
                source_language=source_language,
                target_language=target_language,
                batch_size=self.batch_size
            )

            for i, event in enumerate(translated_subs):
                if i < len(translated_blocks):
                    event.plaintext = translated_blocks[i]

            return original_subs, translated_subs

        except Exception as e:
            logger.error(f"Translation failed for {input_path}: {e}", exc_info=True)
            return None

    @abstractmethod
    async def _translate_batch(
        self,
        texts: List[str],
        source_language: str,
        target_language: str,
        **kwargs
    ) -> List[str]:
        """Translate a batch of text segments."""
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
            logger.warning(f"Error during translator cleanup: {e}")
        except:
            # Ensure we don't raise exceptions during cleanup
            pass
