"""Local NLLB (No Language Left Behind) translator implementation."""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import aiohttp

from .base import BaseTranslator
from ..utils.subtitle_parser import parse_srt_blocks, format_srt_blocks

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
        self.batch_size = int(self.config.get('batch_size', 5))
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
        
        # Read the input file
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Failed to read input file {input_path}: {e}")
            return False
        
        # Parse the subtitle file
        blocks = parse_srt_blocks(lines)
        
        # Extract text blocks for translation
        text_blocks = []
        block_indices = []
        
        for i, block in enumerate(blocks):
            if block['type'] == 'subtitle':
                text_blocks.append(block['content'])
                block_indices.append(i)
        
        if not text_blocks:
            logger.warning(f"No translatable text found in {input_path}")
            # Still create an empty output file
            output_path.write_text('', encoding='utf-8')
            return True
        
        # Translate text blocks in batches
        try:
            translated_blocks = await self._translate_batch(
                text_blocks,
                source_language=source_language,
                target_language=target_language,
                batch_size=self.batch_size
            )
            
            # Update blocks with translated text
            for idx, translated in zip(block_indices, translated_blocks):
                blocks[idx]['content'] = translated
            
            # Write the translated subtitle file
            output_text = format_srt_blocks(blocks)
            output_path.write_text(output_text, encoding='utf-8')
            logger.info(f"Successfully translated {input_path} to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Translation failed: {e}", exc_info=True)
            return False
    
    async def _translate_batch(
        self,
        texts: List[str],
        source_language: str,
        target_language: str,
        batch_size: Optional[int] = None
    ) -> List[str]:
        """Translate a batch of text segments.
        
        Args:
            texts: List of text segments to translate
            source_language: Source language code
            target_language: Target language code
            batch_size: Number of texts to translate in a single request
            
        Returns:
            List of translated text segments
            
        Raises:
            Exception: If translation fails
        """
        if not texts:
            return []
        
        batch_size = batch_size or self.batch_size
        translated_texts = []
        
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Prepare the request payload according to nllb-serve API
            # The API expects 'source' for the text(s) and 'src_lang'/'tgt_lang' for languages
            payload = {
                'source': batch,  # Can be a list of strings
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
                        raise Exception(
                            f"Translation request failed with status {response.status}: {error_text}"
                        )
                    
                    result = await response.json()
                    # The API might return a single string or a list of translations
                    if isinstance(result, str):
                        # Single string response
                        translated_texts.append(result)
                    elif isinstance(result, dict) and 'translation' in result:
                        # Response with 'translation' key
                        if isinstance(result['translation'], list):
                            translated_texts.extend(result['translation'])
                        else:
                            translated_texts.append(result['translation'])
                    elif isinstance(result, list):
                        # Direct list of translations
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
