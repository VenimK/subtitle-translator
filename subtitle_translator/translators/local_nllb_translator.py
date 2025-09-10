"""Local NLLB (No Language Left Behind) translator implementation."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import aiohttp

from .base import BaseTranslator

logger = logging.getLogger(__name__)

class LocalNLLBTranslator(BaseTranslator):
    """Translator using a local NLLB server."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the NLLB translator.
        
        Args:
            config: Configuration dictionary with the following keys:
                - endpoint: URL of the NLLB server
                - batch_size: Number of text segments to translate in a single batch
                - timeout: Request timeout in seconds
        """
        super().__init__(config)
        self.endpoint = self.config.get('endpoint', 'http://localhost:8080/translate')
        self.timeout = aiohttp.ClientTimeout(total=float(self.config.get('timeout', 300)))
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp client session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self.session
    
    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        **kwargs
    ) -> str:
        """Translate a single text string."""
        results = await self._translate_batch(
            [text],
            source_language=source_language,
            target_language=target_language
        )
        return results[0] if results else ""
    
    async def _translate_batch(
        self,
        texts: List[str],
        source_language: str,
        target_language: str,
        **kwargs
    ) -> List[str]:
        """Translate a batch of text segments."""
        if not texts:
            return []
        
        batch_size = kwargs.get('batch_size', self.batch_size)
        translated_texts = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            payload = {
                'source': batch,
                'src_lang': source_language,
                'tgt_lang': target_language
            }
            
            session = await self._get_session()
            
            try:
                async with session.post(
                    self.endpoint,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Translation request failed with status {response.status}: {error_text}")
                    
                    result = await response.json()
                    if isinstance(result, str):
                        translated_texts.append(result)
                    elif isinstance(result, dict) and 'translation' in result:
                        if isinstance(result['translation'], list):
                            translated_texts.extend(result['translation'])
                        else:
                            translated_texts.append(result['translation'])
                    elif isinstance(result, list):
                        translated_texts.extend(result)
                    else:
                        raise Exception(f"Unexpected response format: {result}")
            except asyncio.TimeoutError:
                raise Exception("Translation request timed out")
            except Exception as e:
                logger.error(f"Translation request failed: {e}")
                raise
        
        return translated_texts
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
