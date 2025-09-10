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
    endpoint: str = "http://localhost:6060"  # Default local NLLB server
    api_key: Optional[str] = None
    batch_size: int = 5
    source_language: str = "eng_Latn"
    target_language: str = "nld_Latn"
    timeout: int = 300
    max_retries: int = 3
    retry_delay: int = 5
    gemini_prompt_template: str = "Translate the following text from {source_language} to {target_language}. Please provide only the translated text, without any additional explanations or context. Maintain the original meaning and tone as much as possible."
    gemini_tone: str = ""

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
                'target_language': self.config.target_language,
                'prompt_template': self.config.gemini_prompt_template,
                'tone': self.config.gemini_tone
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
            
            # Map to NLLB language codes (ISO 639-1 to NLLB format)
            lang_map = {
                # Major European languages
                'en': 'eng_Latn',  # English
                'es': 'spa_Latn',  # Spanish
                'fr': 'fra_Latn',  # French
                'de': 'deu_Latn',  # German
                'it': 'ita_Latn',  # Italian
                'pt': 'por_Latn',  # Portuguese
                'ru': 'rus_Cyrl',  # Russian
                'nl': 'nld_Latn',  # Dutch
                'pl': 'pol_Latn',  # Polish
                'uk': 'ukr_Cyrl',  # Ukrainian
                'tr': 'tur_Latn',  # Turkish
                'ar': 'arb_Arab',  # Arabic
                'zh': 'zho_Hans',  # Chinese Simplified
                'zh-tw': 'zho_Hant',  # Chinese Traditional
                'ja': 'jpn_Jpan',  # Japanese
                'ko': 'kor_Hang',  # Korean
                'hi': 'hin_Deva',  # Hindi
                'bn': 'ben_Beng',  # Bengali
                'pa': 'pan_Guru',  # Punjabi
                'ta': 'tam_Taml',  # Tamil
                'te': 'tel_Telu',  # Telugu
                'mr': 'mar_Deva',  # Marathi
                'vi': 'vie_Latn',  # Vietnamese
                'th': 'tha_Thai',  # Thai
                'id': 'ind_Latn',  # Indonesian
                'ms': 'zsm_Latn',  # Malay
                'fil': 'tgl_Latn',  # Filipino
                'sw': 'swh_Latn',  # Swahili
                'ha': 'hau_Latn',  # Hausa
                'yo': 'yor_Latn',  # Yoruba
                'ig': 'ibo_Latn',  # Igbo
                'am': 'amh_Ethi',  # Amharic
                'zu': 'zul_Latn',  # Zulu
                'xh': 'xho_Latn',  # Xhosa
                'st': 'sot_Latn',  # Southern Sotho
                'tn': 'tsn_Latn',  # Tswana
                'sn': 'sna_Latn',  # Shona
                'rw': 'kin_Latn',  # Kinyarwanda
                'mg': 'plt_Latn',  # Malagasy
                'so': 'som_Latn',  # Somali
                'om': 'gaz_Latn',  # Oromo
                'ti': 'tir_Ethi',  # Tigrinya
                'he': 'heb_Hebr',  # Hebrew
                'fa': 'pes_Arab',  # Persian
                'ur': 'urd_Arab',  # Urdu
                'ps': 'pbt_Arab',  # Pashto
                'ku': 'kmr_Latn',  # Kurdish (Kurmanji)
                'ckb': 'ckb_Arab',  # Central Kurdish
                'ne': 'npi_Deva',  # Nepali
                'si': 'sin_Sinh',  # Sinhala
                'km': 'khm_Khmr',  # Khmer
                'lo': 'lao_Laoo',  # Lao
                'my': 'mya_Mymr',  # Burmese
                'ka': 'kat_Geor',  # Georgian
                'hy': 'hye_Armn',  # Armenian
                'az': 'azj_Latn',  # Azerbaijani
                'uz': 'uzn_Latn',  # Uzbek
                'kk': 'kaz_Cyrl',  # Kazakh
                'ky': 'kir_Cyrl',  # Kyrgyz
                'tg': 'tgk_Cyrl',  # Tajik
                'tk': 'tuk_Latn',  # Turkmen
                'mn': 'khk_Cyrl',  # Mongolian
                'bo': 'bod_Tibt',  # Tibetan
                'dz': 'dzo_Tibt',  # Dzongkha
                'ceb': 'ceb_Latn',  # Cebuano
                'jv': 'jav_Latn',  # Javanese
                'su': 'sun_Latn',  # Sundanese
                'ml': 'mal_Mlym',  # Malayalam
                'kn': 'kan_Knda',  # Kannada
                'gu': 'guj_Gujr',  # Gujarati
                'or': 'ory_Orya',  # Odia
                'as': 'asm_Beng',  # Assamese
                'mai': 'mai_Deva',  # Maithili
                'sd': 'snd_Arab',  # Sindhi
                'pa': 'pan_Guru',  # Punjabi (Gurmukhi)
                'si': 'sin_Sinh',  # Sinhala
                'my': 'mya_Mymr',  # Burmese
                'km': 'khm_Khmr',  # Khmer
                'lo': 'lao_Laoo',  # Lao
                'th': 'tha_Thai',  # Thai
                'bo': 'bod_Tibt',  # Tibetan
                'dz': 'dzo_Tibt',  # Dzongkha
            }
            
            # Return the mapped language or default to English if not found
            return lang_map.get(lang, 'eng_Latn')
            
        except Exception as e:
            logger.warning(f"Language detection failed for {file_path}: {e}. Defaulting to English.")
            return 'eng_Latn'

    async def translate_file(
        self,
        input_file: Union[str, Path],
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
        **kwargs
    ):
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

        try:
            return await self.translator.translate_file(
                input_path,
                source_language=src_lang,
                target_language=tgt_lang,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Translation failed: {e}", exc_info=True)
            return None
    
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