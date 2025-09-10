"""Hugging Face translator implementation."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import aiohttp

from .base import BaseTranslator

logger = logging.getLogger(__name__)

class HFTranslator(BaseTranslator):
    """Translator using Hugging Face Inference API."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Hugging Face translator."""
        super().__init__(config)
        self.api_key = self.config.get('api_key', '')
        self.model_name = self.config.get('model_name', 'facebook/nllb-200-distilled-600M')
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_name}"
        self.timeout = aiohttp.ClientTimeout(total=float(self.config.get('timeout', 300)))
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp client session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={
                    'Authorization': f"Bearer {self.api_key}",
                    'Content-Type': 'application/json'
                }
            )
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
        
        session = await self._get_session()
        
        payload = {
            'inputs': texts,
            'options': {'wait_for_model': True}
        }
        if source_language and target_language:
            payload['inputs'] = {
                'text': texts,
                'src_lang': source_language,
                'tgt_lang': target_language
            }

        try:
            async with session.post(self.api_url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Translation request failed with status {response.status}: {error_text}")
                
                result = await response.json()
                
                if isinstance(result, list):
                    return [item.get('translation_text', '') for item in result]
                elif isinstance(result, dict) and 'translation_text' in result:
                    return [result['translation_text']]
                else:
                    raise Exception(f"Unexpected response format: {result}")
                    
        except asyncio.TimeoutError:
            raise Exception("Translation request timed out")
        except Exception as e:
            logger.error(f"Translation request failed: {e}")
            raise
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
