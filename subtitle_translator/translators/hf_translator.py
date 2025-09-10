"""Hugging Face translator implementation."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import aiohttp

from .base import BaseTranslator
from ..utils.subtitle_parser import parse_srt_blocks, format_srt_blocks

logger = logging.getLogger(__name__)

class HFTranslator(BaseTranslator):
    """Translator using Hugging Face Inference API."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Hugging Face translator.
        
        Args:
            config: Configuration dictionary with the following keys:
                - api_key: Hugging Face API key
                - model_name: Name of the model to use (e.g., 'facebook/nllb-200-distilled-600M')
                - batch_size: Number of text segments to translate in a single batch
                - timeout: Request timeout in seconds
        """
        super().__init__(config)
        self.api_key = self.config.get('api_key', '')
        self.model_name = self.config.get('model_name', 'facebook/nllb-200-distilled-600M')
        self.batch_size = int(self.config.get('batch_size', 5))
        self.timeout = aiohttp.ClientTimeout(total=float(self.config.get('timeout', 300)))
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_name}"
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
        """Translate a single text string.
        
        Args:
            text: The text to translate
            source_language: Source language code (e.g., 'eng_Latn')
            target_language: Target language code (e.g., 'nld_Latn')
            **kwargs: Additional parameters (ignored)
            
        Returns:
            The translated text
            
        Raises:
            Exception: If translation fails
        """
        # For single text, just use the batch translation with a single item
        results = await self._translate_batch(
            [text],
            source_language=source_language,
            target_language=target_language
        )
        return results[0] if results else ""
    
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
            **kwargs: Additional parameters (ignored)
            
        Returns:
            bool: True if translation was successful, False otherwise
        """
        input_path = Path(input_file)
        output_path = Path(output_file)

        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Failed to read input file {input_path}: {e}")
            return False

        blocks = parse_srt_blocks(lines)
        text_blocks = [block['content'] for block in blocks if block['type'] == 'subtitle']
        block_indices = [i for i, block in enumerate(blocks) if block['type'] == 'subtitle']

        if not text_blocks:
            output_path.write_text('', encoding='utf-8')
            return True

        try:
            translated_blocks = await self._translate_batch(
                text_blocks,
                source_language=source_language,
                target_language=target_language
            )

            for i, translated in zip(block_indices, translated_blocks):
                blocks[i]['content'] = translated

            output_text = format_srt_blocks(blocks)
            output_path.write_text(output_text, encoding='utf-8')
            return True
        except Exception as e:
            logger.error(f"Translation failed: {e}", exc_info=True)
            return False
    
    async def _translate_batch(
        self,
        texts: List[str],
        source_language: str,
        target_language: str,
        **kwargs
    ) -> List[str]:
        """Translate a batch of text segments.
        
        Args:
            texts: List of text segments to translate
            source_language: Source language code
            target_language: Target language code
            **kwargs: Additional parameters (ignored)
            
        Returns:
            List of translated text segments
            
        Raises:
            Exception: If translation fails
        """
        if not texts:
            return []
        
        session = await self._get_session()
        
        # Prepare the request payload for Hugging Face API
        payload = {
            'inputs': {
                'text': texts,
                'src_lang': source_language,
                'tgt_lang': target_language
            },
            'options': {
                'use_cache': True,
                'wait_for_model': True
            }
        }
        
        try:
            async with session.post(
                self.api_url,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Translation request failed with status {response.status}: {error_text}"
                    )
                
                result = await response.json()
                
                # Handle different response formats from Hugging Face
                if isinstance(result, list):
                    # Direct list of translations
                    return [item.get('translation_text', '') for item in result]
                elif isinstance(result, dict) and 'translation_text' in result:
                    # Single translation result
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
