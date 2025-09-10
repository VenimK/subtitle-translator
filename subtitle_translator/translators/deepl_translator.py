"""DeepL translator implementation."""

import asyncio
import logging
from typing import Dict, Any, List, Optional

import deepl

from .base import BaseTranslator

logger = logging.getLogger(__name__)

class DeepLTranslator(BaseTranslator):
    """Translator using the DeepL API."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the DeepL translator."""
        super().__init__(config)
        self.api_key = self.config.get('api_key')
        self.translator = None
        if self.api_key:
            self.translator = deepl.Translator(self.api_key)

    async def translate_text(
        self, text: str, source_language: str, target_language: str, **kwargs
    ) -> str:
        """Translate a single text string using DeepL."""
        if not self.translator:
            raise ConnectionError("DeepL API key not configured.")

        # DeepL uses 2-letter language codes, so we extract them.
        src_lang = source_language[:2].upper()
        tgt_lang = target_language[:2].upper()

        try:
            result = await asyncio.to_thread(
                self.translator.translate_text,
                text,
                source_lang=src_lang,
                target_lang=tgt_lang
            )
            return result.text
        except Exception as e:
            logger.error(f"DeepL translation failed: {e}", exc_info=True)
            raise

    async def _translate_batch(
        self, texts: List[str], source_language: str, target_language: str, **kwargs
    ) -> List[str]:
        """Translate a batch of texts using DeepL."""
        if not self.translator:
            raise ConnectionError("DeepL API key not configured.")

        src_lang = source_language[:2].upper()
        tgt_lang = target_language[:2].upper()

        try:
            results = await asyncio.to_thread(
                self.translator.translate_text,
                texts,
                source_lang=src_lang,
                target_lang=tgt_lang
            )
            return [r.text for r in results]
        except Exception as e:
            logger.error(f"DeepL batch translation failed: {e}", exc_info=True)
            raise
