"""Core translator functionality for the subtitle translator."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import asyncio
import json
import logging
from langdetect import detect
import re

from ..utils.config import ConfigManager
from ..translators import TranslatorFactory
from .exceptions import TranslationError, ConfigurationError

logger = logging.getLogger(__name__)

@dataclass
class TranslationConfig:
    """Configuration for subtitle translation."""
    translator_type: str = "local_nllb"
    endpoint: str = "https://check.nas86.eu/"
    api_key: Optional[str] = None
    batch_size: int = 5
    source_language: str = "eng_Latn"
    target_language: str = "nld_Latn"
    timeout: int = 300
    max_retries: int = 3
    retry_delay: int = 5

@dataclass
class TranslationResult:
    """Result of a translation operation."""
    success: bool
    input_file: Path
    output_file: Path
    source_language: str
    target_language: str
    error: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None

class Translator:
    """Main translator class for handling subtitle translations."""
    
    def __init__(self, config: Optional[TranslationConfig] = None):
        """Initialize the translator with the given configuration."""
        self.config = config or TranslationConfig()
        self.translator = None
        self._initialize_translator()
    
    def _initialize_translator(self):
        """Initialize the underlying translator engine."""
        try:
            translator_config = {
                'endpoint': self.config.endpoint,
                'api_key': self.config.api_key,
                'batch_size': self.config.batch_size,
                'timeout': self.config.timeout,
                'source_language': self.config.source_language,
                'target_language': self.config.target_language
            }
            self.translator = TranslatorFactory.create_translator(
                self.config.translator_type,
                translator_config
            )
        except Exception as e:
            logger.error(f"Failed to initialize translator: {e}")
            raise ConfigurationError(f"Failed to initialize translator: {e}")

    def _detect_language(self, file_path: Path) -> str:
        """Detect the language of a subtitle file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Read a sample of the file (e.g., the first 100 lines)
                lines = [next(f) for _ in range(100)]
            
            # Join the lines and remove timestamps and other SRT artifacts
            text = " ".join(lines)
            text = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', text)
            text = re.sub(r'<[^>]+>', '', text)  # Remove HTML-like tags
            
            # Detect the language
            lang = detect(text)
            
            # Map to NLLB language codes (this is a simplified mapping)
            lang_map = {
                'en': 'eng_Latn',
                'nl': 'nld_Latn',
                'fr': 'fra_Latn',
                'de': 'deu_Latn',
                'es': 'spa_Latn',
                # Add more mappings as needed
            }
            
            return lang_map.get(lang, 'eng_Latn')  # Default to English
            
        except Exception as e:
            logger.warning(f"Language detection failed for {file_path}: {e}. Defaulting to English.")
            return 'eng_Latn'

    async def translate_file(
        self,
        input_file: Union[str, Path],
        output_file: Optional[Union[str, Path]] = None,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
        **kwargs
    ) -> TranslationResult:
        """
        Translate a subtitle file.
        """
        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        src_lang = source_language or self.config.source_language
        if src_lang == 'auto':
            src_lang = self._detect_language(input_path)
            logger.info(f"Detected source language for {input_path.name}: {src_lang}")

        tgt_lang = target_language or self.config.target_language
        
        if output_file is None:
            # Remove any existing language code from the filename
            stem = input_path.stem
            # Pattern to match language codes like .eng, _eng, .spa, _spa, etc.
            import re
            # First try to match common patterns with dots or underscores
            stem = re.sub(r'[._](eng|spa|nld|deu|fra|ita|por|rus|jpn|kor|zho|ara|tur|pol|ukr|swe|dan|nor|fin|hun|ces|ron|ell|bul|srp|hrv|slv|mkd|bos)(?:_[A-Za-z]{4,5})?$', '', stem)
            # Also handle cases where the code might be at the end after a track number
            stem = re.sub(r'[._]track\d+[._](eng|spa|nld|deu|fra|ita|por|rus|jpn|kor|zho|ara|tur|pol|ukr|swe|dan|nor|fin|hun|ces|ron|ell|bul|srp|hrv|slv|mkd|bos)(?:_[A-Za-z]{4,5})?$', '', stem)
            # Add the new target language code with an underscore
            output_path = input_path.with_name(f"{stem}_{tgt_lang}{input_path.suffix}")
        else:
            output_path = Path(output_file)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        result = TranslationResult(
            success=False,
            input_file=input_path,
            output_file=output_path,
            source_language=src_lang,
            target_language=tgt_lang
        )
        
        try:
            success = await self.translator.translate_file(
                input_path,
                output_path,
                source_language=src_lang,
                target_language=tgt_lang,
                **kwargs
            )
            
            result.success = bool(success)
            if not success:
                result.error = "Translation failed with no error message"
            
            return result
            
        except Exception as e:
            result.error = str(e)
            logger.error(f"Translation failed: {e}", exc_info=True)
            return result
    
    def update_config(self, **kwargs):
        """Update the translator configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self._initialize_translator()
    
    async def close(self):
        """Close any resources used by the translator."""
        if hasattr(self.translator, 'close'):
            if asyncio.iscoroutinefunction(self.translator.close):
                await self.translator.close()
            else:
                self.translator.close()

    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()