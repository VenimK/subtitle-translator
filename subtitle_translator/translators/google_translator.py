"""Google Translate implementation."""

import logging
from typing import Dict, Any, Optional, List

from google.cloud import translate_v2 as translate

from .base import BaseTranslator

logger = logging.getLogger(__name__)

class GoogleTranslator(BaseTranslator):
    """Translator using Google Cloud Translation API."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Google translator."""
        super().__init__(config)
        self.client = translate.Client()
    
    async def _translate_batch(
        self,
        texts: List[str],
        source_language: str,
        target_language: str,
        **kwargs
    ) -> List[str]:
        """Translate a batch of text strings using Google Translate."""
        try:
            # The v2 API uses language codes without the script part (e.g., 'en' instead of 'eng_Latn')
            source_lang_short = source_language.split('_')[0]
            target_lang_short = target_language.split('_')[0]

            results = self.client.translate(
                texts,
                source_language=source_lang_short,
                target_language=target_lang_short
            )
            return [result['translatedText'] for result in results]
        except Exception as e:
            logger.error(f"Google Translate batch failed: {e}", exc_info=True)
            raise
