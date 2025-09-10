"""Google Translate implementation."""

import logging
from typing import Dict, Any, Optional

from google.cloud import translate_v2 as translate

from .base import BaseTranslator

logger = logging.getLogger(__name__)

class GoogleTranslator(BaseTranslator):
    """Translator using Google Cloud Translation API."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Google translator."""
        super().__init__(config)
        self.client = translate.Client()
    
    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        **kwargs
    ) -> str:
        """Translate a single text string using Google Translate."""
        try:
            result = self.client.translate(
                text,
                source_language=source_language,
                target_language=target_language
            )
            return result['translatedText']
        except Exception as e:
            logger.error(f"Google Translate failed: {e}", exc_info=True)
            raise
