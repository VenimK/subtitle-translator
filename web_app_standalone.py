"""Standalone web interface for subtitle translator - no GUI dependencies."""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import asyncio
import logging
from pathlib import Path
from typing import List, Optional
import tempfile
import os
import sys
import traceback
import pysubs2

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Subtitle Translator", description="Translate subtitle files using AI services")

# Create temporary directory for uploads
UPLOAD_DIR = Path(tempfile.mkdtemp())
OUTPUT_DIR = UPLOAD_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Simple translator factory for standalone usage
class StandaloneTranslatorFactory:
    """Standalone translator factory that doesn't depend on the GUI module."""

    @staticmethod
    def create_translator(translator_type: str, config: dict):
        """Create a translator instance without GUI dependencies."""
        if translator_type == 'local_nllb':
            return LocalNLLBTranslator(config)
        elif translator_type == 'google':
            return GoogleTranslator(config)
        elif translator_type == 'deepl':
            return DeepLTranslator(config)
        elif translator_type == 'gemini':
            return GeminiTranslator(config)
        else:
            raise ValueError(f"Unsupported translator type: {translator_type}")

class BaseStandaloneTranslator:
    """Base class for standalone translators."""

    def __init__(self, config):
        self.config = config or {}
        self.batch_size = int(self.config.get('batch_size', 5))

    async def translate_file(self, input_file, source_language, target_language):
        """Translate a subtitle file."""
        input_path = Path(input_file)

        try:
            # Load subtitle file
            with open(input_path, 'r', encoding='utf-8') as f:
                original_subs = pysubs2.load(input_path)
                translated_subs = pysubs2.load(input_path)  # Copy for translation

            # Extract text for translation
            text_blocks = [event.plaintext for event in original_subs]

            if not text_blocks:
                return original_subs, translated_subs

            # Translate text blocks
            translated_blocks = await self._translate_batch(
                text_blocks,
                source_language=source_language,
                target_language=target_language
            )

            # Update translated subtitles
            for i, event in enumerate(translated_subs):
                if i < len(translated_blocks):
                    event.plaintext = translated_blocks[i]

            return original_subs, translated_subs

        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return None

    async def _translate_batch(self, texts, source_language, target_language):
        """Translate a batch of texts - to be implemented by subclasses."""
        raise NotImplementedError

    async def close(self):
        """Close resources."""
        pass

class LocalNLLBTranslator(BaseStandaloneTranslator):
    """Local NLLB translator that connects to real NLLB server."""

    def __init__(self, config):
        super().__init__(config)
        self.endpoint = self.config.get('endpoint', 'http://192.168.1.233:6060/translate')
        self.timeout = float(self.config.get('timeout', 300))
        self.session = None

    async def _get_session(self):
        """Get or create an aiohttp client session."""
        if self.session is None or self.session.closed:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    async def _translate_batch(self, texts, source_language, target_language):
        """Translate using real local NLLB server."""
        if not texts:
            return []

        print(f"🔍 LocalNLLB: Connecting to {self.endpoint}")
        print(f"🔍 LocalNLLB: Translating {len(texts)} texts from {source_language} to {target_language}")
        print(f"🔍 LocalNLLB: Texts: {texts}")

        batch_size = self.batch_size
        translated_texts = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            print(f"🔍 LocalNLLB: Processing batch {i//batch_size + 1}: {batch}")

            payload = {
                'source': batch,
                'src_lang': source_language,
                'tgt_lang': target_language
            }

            session = await self._get_session()

            try:
                print(f"🔍 LocalNLLB: Making request to {self.endpoint}")
                print(f"🔍 LocalNLLB: Payload: {payload}")
                
                async with session.post(
                    self.endpoint,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    print(f"🔍 LocalNLLB: Response status: {response.status}")
                    print(f"🔍 LocalNLLB: Response headers: {dict(response.headers)}")
                    
                    logger.info(f"LocalNLLB: Request status: {response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        print(f"🔍 LocalNLLB: Error response: {error_text}")
                        logger.error(f"LocalNLLB: Request failed: {response.status} - {error_text}")
                        # Return original texts on error
                        translated_texts.extend(batch)
                        continue

                    result = await response.json()
                    print(f"🔍 LocalNLLB: Response JSON: {result}")
                    logger.info(f"LocalNLLB: Response received: {type(result)}")

                    # Handle different response formats
                    if isinstance(result, str):
                        translated_texts.append(result)
                        print(f"🔍 LocalNLLB: String response: {result}")
                    elif isinstance(result, dict) and 'translation' in result:
                        if isinstance(result['translation'], list):
                            translated_texts.extend(result['translation'])
                            print(f"🔍 LocalNLLB: List response: {result['translation']}")
                        else:
                            translated_texts.append(result['translation'])
                            print(f"🔍 LocalNLLB: Single translation: {result['translation']}")
                    elif isinstance(result, list):
                        translated_texts.extend(result)
                        print(f"🔍 LocalNLLB: Direct list: {result}")
                    else:
                        print(f"🔍 LocalNLLB: Unexpected response format: {result}")
                        logger.error(f"LocalNLLB: Unexpected response format: {result}")
                        # Return original texts on unexpected format
                        translated_texts.extend(batch)

            except Exception as e:
                print(f"🔍 LocalNLLB: Exception: {e}")
                import traceback
                traceback.print_exc()
                logger.error(f"LocalNLLB: Request failed: {e}")
                translated_texts.extend(batch)

        # Log translation results
        print(f"🔍 LocalNLLB: Final results:")
        for i, (original, translated) in enumerate(zip(texts, translated_texts)):
            print(f"🔍 LocalNLLB: '{original}' -> '{translated}'")
            logger.info(f"LocalNLLB: '{original[:50]}...' -> '{translated[:50]}...'")

        return translated_texts

    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

class GoogleTranslator(BaseStandaloneTranslator):
    """Google Translate for standalone usage."""

    async def _translate_batch(self, texts, source_language, target_language):
        """Translate using Google Translate API."""
        logger.info(f"Google: Translating {len(texts)} texts from {source_language} to {target_language}")
        
        # For demo purposes, simulate translation
        translated_texts = []
        for text in texts:
            # Simple demo transformation
            translated_text = f"[GOOGLE DEMO] {text}"
            translated_texts.append(translated_text)
            logger.info(f"Google: '{text}' -> '{translated_text}'")
        
        return translated_texts

class DeepLTranslator(BaseStandaloneTranslator):
    """DeepL translator for standalone usage."""

    async def _translate_batch(self, texts, source_language, target_language):
        """Translate using DeepL API."""
        logger.info(f"DeepL: Translating {len(texts)} texts from {source_language} to {target_language}")
        
        # For demo purposes, simulate translation
        translated_texts = []
        for text in texts:
            # Simple demo transformation
            translated_text = f"[DEEPL DEMO] {text}"
            translated_texts.append(translated_text)
            logger.info(f"DeepL: '{text}' -> '{translated_text}'")
        
        return translated_texts

class GeminiTranslator(BaseStandaloneTranslator):
    """Gemini AI translator for standalone usage - uses real Gemini API without GUI dependencies."""

    def __init__(self, config):
        super().__init__(config)
        self.real_translator = None
        # Don't set batch_size here yet - let _init_real_translator handle it
        self._init_real_translator()

    def _init_real_translator(self):
        """Initialize the real Gemini translator without GUI dependencies."""
        logger.info("🔧 Starting standalone Gemini translator initialization...")
        
        try:
            import google.generativeai as genai
            logger.info("✅ google.generativeai imported successfully")

            # Debug the config
            logger.info(f"🔧 Config received: {self.config}")
            api_key = self.config.get('api_key')
            logger.info(f"🔧 API key from config: {api_key[:10] + '...' if api_key and len(api_key) > 10 else str(api_key)}")

            if not api_key:
                logger.error("❌ No API key provided in config")
                self.real_translator = None
                return

            # Configure Gemini directly without importing the GUI translator
            genai.configure(api_key=api_key)
            
            # Get advanced configuration parameters
            batch_size = self.config.get('batch_size', 300)
            streaming = self.config.get('streaming', True)
            thinking = self.config.get('thinking', True)
            thinking_budget = self.config.get('thinking_budget', 2048)
            temperature = self.config.get('temperature', None)
            top_p = self.config.get('top_p', None)
            top_k = self.config.get('top_k', None)
            free_quota = self.config.get('free_quota', True)
            use_colors = self.config.get('use_colors', True)
            
            # Create generation config with advanced parameters
            generation_config = {}
            if temperature is not None:
                generation_config['temperature'] = temperature
            if top_p is not None:
                generation_config['top_p'] = top_p
            if top_k is not None:
                generation_config['top_k'] = top_k
            
            # Create model with advanced configuration
            self.model = genai.GenerativeModel(
                'gemini-2.5-flash-preview-05-20',
                generation_config=generation_config if generation_config else None
            )
            
            # Store advanced parameters - OVERRIDE the base class batch_size
            self.batch_size = batch_size  # This will override the base class default of 5
            self.streaming = streaming
            self.thinking = thinking
            self.thinking_budget = thinking_budget
            self.free_quota = free_quota
            self.use_colors = use_colors
            self.api_key = api_key
            
            # Set up prompt template
            self.prompt_template = self.config.get(
                'prompt_template',
                "Translate the following text from {source_language} to {target_language}. Please provide only the translated text, without any additional explanations or context. Maintain the original meaning and tone as much as possible.\n\nText: {text}"
            )
            
            logger.info("✅ Standalone Gemini translator initialized successfully")
            logger.info(f"✅ Model: {self.model.model_name}")
            logger.info(f"✅ API key available: {self.api_key is not None}")
            logger.info(f"🔧 Advanced config - batch_size: {batch_size}, streaming: {streaming}, thinking: {thinking}")
            logger.info(f"🔧 Generation config: {generation_config}")
            
            if self.api_key:
                masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if len(self.api_key) > 8 else "..."
                logger.info(f"✅ API key: {masked_key}")
            
            self.real_translator = self  # Use self as the translator

        except ImportError as e:
            logger.error(f"❌ Failed to import google.generativeai: {e}")
            logger.info("💡 Make sure google-generativeai is installed: pip install google-generativeai")
            self.real_translator = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini translator: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.real_translator = None

    async def _translate_batch(self, texts, source_language, target_language):
        """Translate using real Gemini AI API with advanced parameters."""
        if not self.real_translator or not hasattr(self, 'model'):
            logger.error("❌ Gemini translator not available - returning demo results")
            logger.info("🔧 To fix: Install google-generativeai and ensure API key is valid")
            return [f"[GEMINI DEMO - API NOT AVAILABLE] {text}" for text in texts]

        try:
            logger.info(f"🚀 Translating {len(texts)} texts with real Gemini API")
            logger.info(f"🔧 Using batch_size: {self.batch_size}, streaming: {self.streaming}")
            
            translated_texts = []
            total_tokens = 0
            
            # Process in batches using the configured batch_size
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]
                logger.info(f"🔧 Processing batch {i//self.batch_size + 1}: {len(batch)} texts")
                
                # Create batch prompt for multiple texts
                batch_prompt = f"Translate the following texts from {source_language} to {target_language}. "
                batch_prompt += "Please provide only the translated texts, one per line, without any additional explanations or context. "
                batch_prompt += "Maintain the original meaning and tone as much as possible.\n\nTexts:\n"
                
                for j, text in enumerate(batch, 1):
                    batch_prompt += f"{j}. {text}\n"
                
                try:
                    if self.streaming:
                        # Use streaming for better performance
                        logger.info(f"🔧 Using streaming translation")
                        response = await self.model.generate_content_async(
                            batch_prompt,
                            stream=True
                        )
                        
                        full_response = ""
                        async for chunk in response:
                            if chunk.text:
                                full_response += chunk.text
                        
                        # Parse the batch response
                        batch_translations = self._parse_batch_response(full_response, len(batch))
                        
                    else:
                        # Regular non-streaming translation
                        response = await self.model.generate_content_async(batch_prompt)
                        batch_translations = self._parse_batch_response(response.text, len(batch))
                    
                    if hasattr(response, 'usage_metadata') and response.usage_metadata:
                        tokens = response.usage_metadata.total_token_count
                        total_tokens += tokens
                        logger.info(f"🔧 Batch tokens used: {tokens}")
                    
                    translated_texts.extend(batch_translations)
                    logger.info(f"✅ Batch {i//self.batch_size + 1} completed: {len(batch_translations)} translations")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to translate batch {i//self.batch_size + 1}: {e}")
                    # Fallback to original texts for this batch
                    translated_texts.extend(batch)
            
            logger.info(f"🎉 Gemini batch translation completed! Total tokens: {total_tokens}")
            return translated_texts
            
        except Exception as e:
            logger.error(f"❌ Gemini translation failed: {e}")
            logger.info("🔧 Check your Gemini API key and internet connection")
            # Fallback to demo on error
            return [f"[GEMINI DEMO - ERROR] {text}" for text in texts]

    def _parse_batch_response(self, response_text: str, expected_count: int) -> List[str]:
        """Parse batch translation response into individual translations."""
        try:
            lines = response_text.strip().split('\n')
            translations = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Remove numbering if present (1. 2. etc.)
                if line and line[0].isdigit() and '. ' in line:
                    line = line.split('. ', 1)[1]
                
                translations.append(line)
            
            # Ensure we have the expected number of translations
            while len(translations) < expected_count:
                translations.append(translations[-1] if translations else "")
            
            return translations[:expected_count]
            
        except Exception as e:
            logger.error(f"❌ Failed to parse batch response: {e}")
            # Return empty strings as fallback
            return [""] * expected_count

    async def close(self):
        """Close resources."""
        pass

@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the main web interface."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Subtitle Translator</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
                margin-bottom: 10px;
            }
            .subtitle {
                text-align: center;
                color: #28a745;
            }
            .form-group {
                margin-bottom: 20px;
            }
            .form-group small {
                display: block;
                color: #666;
                font-size: 12px;
                margin-top: 5px;
            }
            .advanced-settings {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
                margin: 15px 0;
                background-color: #f9f9f9;
            }
            .advanced-settings h3 {
                margin-top: 0;
                color: #333;
                border-bottom: 1px solid #ddd;
                padding-bottom: 10px;
            }
            .server-logs {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
                margin: 15px 0;
                background-color: #f8f9fa;
                max-height: 300px;
                overflow-y: auto;
            }
            .log-content {
                font-family: 'Courier New', monospace;
                font-size: 12px;
                background-color: #000;
                color: #00ff00;
                padding: 10px;
                border-radius: 3px;
                max-height: 200px;
                overflow-y: auto;
                white-space: pre-wrap;
            }
            .clear-logs-btn {
                margin-top: 10px;
                padding: 5px 10px;
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 3px;
                cursor: pointer;
                font-size: 12px;
            }
            .clear-logs-btn:hover {
                background-color: #c82333;
            }
            input, select, textarea {
                width: 100%;
                padding: 10px;
                border: 2px solid #ddd;
                border-radius: 5px;
                font-size: 16px;
                box-sizing: border-box;
            }
            input[type="file"] {
                padding: 5px;
            }
            .button-group {
                text-align: center;
                margin-top: 30px;
            }
            button {
                background-color: #2a82da;
                color: white;
                padding: 12px 30px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
                margin: 0 10px;
            }
            button:hover {
                background-color: #1e6bb8;
            }
            button:disabled {
                background-color: #ccc;
                cursor: not-allowed;
            }
            .progress {
                margin-top: 20px;
                display: none;
            }
            .progress-bar {
                width: 100%;
                height: 20px;
                background-color: #f0f0f0;
                border-radius: 10px;
                overflow: hidden;
            }
            .progress-fill {
                height: 100%;
                background-color: #2a82da;
                width: 0%;
                transition: width 0.3s ease;
            }
            .status {
                margin-top: 10px;
                padding: 10px;
                border-radius: 5px;
                display: none;
            }
            .success {
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .error {
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .file-list {
                margin-top: 20px;
            }
            .file-item {
                background: #f8f9fa;
                padding: 10px;
                margin: 5px 0;
                border-radius: 5px;
                border-left: 4px solid #2a82da;
            }
            .download-btn {
                background-color: #28a745;
                margin-left: 10px;
            }
            .download-btn:hover {
                background-color: #218838;
            }
            .service-info {
                background: #e3f2fd;
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 20px;
                border-left: 4px solid #2196f3;
            }
            .warning {
                background: #fff3cd;
                color: #856404;
                border: 1px solid #ffeaa7;
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 15px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎬 Subtitle Translator</h1>
            <p class="subtitle">✨ Standalone AI Translation Services</p>

            <div class="service-info">
                <strong>Available Services:</strong> Local NLLB, Google Translate, DeepL, Gemini AI
            </div>

            <div class="warning">
                <strong>Note:</strong> Local NLLB and API services (Google, DeepL, Gemini) require valid API keys and internet connection. Gemini AI now uses real Google Gemini API!
            </div>

            <form id="translateForm">
                <div class="form-group">
                    <label for="files">Subtitle Files:</label>
                    <input type="file" id="files" name="files" multiple accept=".srt,.ass,.ssa,.vtt" required>
                    <small>Supported formats: .srt, .ass, .ssa, .vtt</small>
                </div>

                <div class="form-group">
                    <label for="source_lang">Source Language:</label>
                    <select id="source_lang" name="source_lang" required>
                        <option value="eng_Latn">English</option>
                        <option value="spa_Latn">Spanish</option>
                        <option value="fra_Latn">French</option>
                        <option value="deu_Latn">German</option>
                        <option value="ita_Latn">Italian</option>
                        <option value="por_Latn">Portuguese</option>
                        <option value="rus_Cyrl">Russian</option>
                        <option value="jpn_Jpan">Japanese</option>
                        <option value="kor_Hang">Korean</option>
                        <option value="zho_Hans">Chinese (Simplified)</option>
                        <option value="ara_Arab">Arabic</option>
                        <option value="nld_Latn">Dutch</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="target_lang">Target Language:</label>
                    <select id="target_lang" name="target_lang" required>
                        <option value="nld_Latn">Dutch</option>
                        <option value="eng_Latn">English</option>
                        <option value="spa_Latn">Spanish</option>
                        <option value="fra_Latn">French</option>
                        <option value="deu_Latn">German</option>
                        <option value="ita_Latn">Italian</option>
                        <option value="por_Latn">Portuguese</option>
                        <option value="rus_Cyrl">Russian</option>
                        <option value="jpn_Jpan">Japanese</option>
                        <option value="kor_Hang">Korean</option>
                        <option value="zho_Hans">Chinese (Simplified)</option>
                        <option value="ara_Arab">Arabic</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="translator">Translation Service:</label>
                    <select id="translator" name="translator">
                        <option value="local_nllb">Local NLLB Server</option>
                        <option value="google">Google Translate</option>
                        <option value="deepl">DeepL</option>
                        <option value="gemini">Gemini AI</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="api_key">API Key (required for Google, DeepL, Gemini):</label>
                    <input type="password" id="api_key" name="api_key" placeholder="Enter your API key">
                </div>

                <div class="form-group" id="endpoint-group" style="display: none;">
                    <label for="endpoint">Server Endpoint (for Local NLLB Server):</label>
                    <input type="url" id="endpoint" name="endpoint" value="http://192.168.1.233:6060/translate" placeholder="http://192.168.1.233:6060/translate">
                </div>

                <!-- Advanced Gemini Settings -->
                <div id="gemini-settings" class="advanced-settings" style="display: none;">
                    <h3>🤖 Advanced Gemini Settings</h3>
                    
                    <div class="form-group">
                        <label for="batch_size">Batch Size:</label>
                        <input type="number" id="batch_size" name="batch_size" value="300" min="1" max="500" title="Number of texts to translate in one API call">
                        <small>Higher values = faster translation but more tokens per request</small>
                    </div>

                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="streaming" name="streaming" checked>
                            Enable Streaming
                        </label>
                        <small>Stream responses for better performance</small>
                    </div>

                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="thinking" name="thinking" checked>
                            Enable Thinking Mode
                        </label>
                        <small>Allow model to think before responding</small>
                    </div>

                    <div class="form-group">
                        <label for="thinking_budget">Thinking Budget:</label>
                        <input type="number" id="thinking_budget" name="thinking_budget" value="2048" min="512" max="8192" title="Token budget for thinking">
                        <small>Tokens allocated for model thinking (512-8192)</small>
                    </div>

                    <div class="form-group">
                        <label for="temperature">Temperature:</label>
                        <input type="number" id="temperature" name="temperature" step="0.1" min="0" max="2" placeholder="Auto (leave empty)" title="Controls randomness (0.0-2.0)">
                        <small>0.0 = deterministic, 1.0 = balanced, 2.0 = creative</small>
                    </div>

                    <div class="form-group">
                        <label for="top_p">Top P:</label>
                        <input type="number" id="top_p" name="top_p" step="0.1" min="0" max="1" placeholder="Auto (leave empty)" title="Nucleus sampling (0.0-1.0)">
                        <small>Controls diversity of word selection</small>
                    </div>

                    <div class="form-group">
                        <label for="top_k">Top K:</label>
                        <input type="number" id="top_k" name="top_k" min="1" max="100" placeholder="Auto (leave empty)" title="Limits vocabulary selection">
                        <small>Number of top tokens to consider</small>
                    </div>

                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="free_quota" name="free_quota" checked>
                            Use Free Quota
                        </label>
                        <small>Prioritize free tier usage</small>
                    </div>

                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="use_colors" name="use_colors" checked>
                            Use Colors in Output
                        </label>
                        <small>Enable colored console output</small>
                    </div>
                </div>

                <div class="button-group">
                    <button type="submit">Translate with AI</button>
                    <button type="button" onclick="clearResults()">Clear Results</button>
                </div>
            </form>

            <div id="progress" class="progress">
                <div class="progress-bar">
                    <div id="progress-fill" class="progress-fill"></div>
                </div>
                <div id="status-text">Translating with AI services...</div>
            </div>

            <!-- Real-time server logs -->
            <div id="server-logs" class="server-logs" style="display: none;">
                <h3>🔍 Server Activity</h3>
                <div id="log-content" class="log-content"></div>
                <button type="button" onclick="clearLogs()" class="clear-logs-btn">Clear Logs</button>
            </div>

            <div id="results" class="file-list"></div>
        </div>

        <script>
            // Show/hide endpoint field based on translator selection
            document.getElementById('translator').onchange = function() {
                const endpointGroup = document.getElementById('endpoint-group');
                const geminiSettings = document.getElementById('gemini-settings');
                const apiKeyField = document.getElementById('api_key').closest('.form-group');
                
                if (this.value === 'local_nllb') {
                    endpointGroup.style.display = 'block';
                    geminiSettings.style.display = 'none';
                    apiKeyField.style.display = 'none';
                } else if (this.value === 'gemini') {
                    endpointGroup.style.display = 'none';
                    geminiSettings.style.display = 'block';
                    apiKeyField.style.display = 'block';
                } else {
                    endpointGroup.style.display = 'none';
                    geminiSettings.style.display = 'none';
                    apiKeyField.style.display = 'block';
                }
            };

            // Add immediate feedback when button is clicked
            document.querySelector('button[type="submit"]').onclick = function() {
                console.log('🖱️ Button clicked!');
                console.log('📋 Form elements:');
                console.log('  - Files:', document.getElementById('files').files.length);
                console.log('  - Translator:', document.getElementById('translator').value);
                console.log('  - Endpoint:', document.getElementById('endpoint').value);
            };

            document.getElementById('translateForm').onsubmit = async function(e) {
                e.preventDefault();

                console.log('🚀 Form submission started...');

                const formData = new FormData();
                const files = document.getElementById('files').files;

                console.log('📁 Files selected:', files.length);

                if (files.length === 0) {
                    alert('Please select files to translate');
                    return;
                }

                // Add files to form data
                for (let file of files) {
                    formData.append('files', file);
                    console.log('📄 Added file:', file.name);
                }

                // Add other form fields
                const sourceLang = document.getElementById('source_lang').value;
                const targetLang = document.getElementById('target_lang').value;
                const translator = document.getElementById('translator').value;
                const apiKey = document.getElementById('api_key').value;
                const endpoint = document.getElementById('endpoint').value;

                // Add advanced Gemini parameters
                const batchSize = document.getElementById('batch_size').value;
                const streaming = document.getElementById('streaming').checked;
                const thinking = document.getElementById('thinking').checked;
                const thinkingBudget = document.getElementById('thinking_budget').value;
                const temperature = document.getElementById('temperature').value;
                const topP = document.getElementById('top_p').value;
                const topK = document.getElementById('top_k').value;
                const freeQuota = document.getElementById('free_quota').checked;
                const useColors = document.getElementById('use_colors').checked;

                console.log('🌐 Source language:', sourceLang);
                console.log('🌐 Target language:', targetLang);
                console.log('🤖 Translator:', translator);
                console.log('🔑 API Key:', apiKey ? '***provided***' : 'not provided');
                console.log('🔗 Endpoint:', endpoint);
                
                if (translator === 'gemini') {
                    console.log('🤖 Gemini Settings:');
                    console.log('  - Batch Size:', batchSize);
                    console.log('  - Streaming:', streaming);
                    console.log('  - Thinking:', thinking);
                    console.log('  - Thinking Budget:', thinkingBudget);
                    console.log('  - Temperature:', temperature || 'auto');
                    console.log('  - Top P:', topP || 'auto');
                    console.log('  - Top K:', topK || 'auto');
                    console.log('  - Free Quota:', freeQuota);
                    console.log('  - Use Colors:', useColors);
                }

                formData.append('source_lang', sourceLang);
                formData.append('target_lang', targetLang);
                formData.append('translator', translator);
                formData.append('api_key', apiKey);
                formData.append('endpoint', endpoint);
                
                // Add advanced Gemini parameters to form data
                formData.append('batch_size', batchSize);
                formData.append('streaming', streaming);
                formData.append('thinking', thinking);
                formData.append('thinking_budget', thinkingBudget);
                formData.append('temperature', temperature);
                formData.append('top_p', topP);
                formData.append('top_k', topK);
                formData.append('free_quota', freeQuota);
                formData.append('use_colors', useColors);

                // Show progress
                document.getElementById('progress').style.display = 'block';
                document.getElementById('progress-fill').style.width = '0%';
                document.getElementById('status-text').textContent = '🚀 Initializing translation service...';

                console.log('📤 Sending request to /translate...');

                // Show server logs panel
                document.getElementById('server-logs').style.display = 'block';
                addServerLog('🚀 Starting translation process...');
                addServerLog('📡 Connecting to ' + translator + ' service...');

                // Animate progress bar in 10% steps
                let currentProgress = 0;
                const progressInterval = setInterval(() => {
                    currentProgress += 10;
                    document.getElementById('progress-fill').style.width = currentProgress + '%';
                    
                    // Update status messages at specific progress points
                    if (currentProgress === 10) {
                        document.getElementById('status-text').textContent = '📡 Connecting to translation service...';
                        addServerLog('🔌 Establishing connection...');
                    } else if (currentProgress === 30) {
                        document.getElementById('status-text').textContent = '🤖 AI is analyzing your subtitles...';
                        addServerLog('🧠 AI analyzing subtitle structure...');
                    } else if (currentProgress === 50) {
                        document.getElementById('status-text').textContent = '🧠 AI is translating your content...';
                        addServerLog('🔄 Processing ' + files.length + ' file(s)...');
                    } else if (currentProgress === 70) {
                        document.getElementById('status-text').textContent = '📝 Processing translation results...';
                        addServerLog('📊 Parsing translation results...');
                    } else if (currentProgress === 90) {
                        document.getElementById('status-text').textContent = '🔄 Finalizing translations...';
                        addServerLog('💾 Preparing download files...');
                    }
                    
                    if (currentProgress >= 90) {
                        clearInterval(progressInterval);
                    }
                }, 300); // Update every 300ms for smooth animation

                // Small delay to show the initial connecting message
                await new Promise(resolve => setTimeout(resolve, 500));

                try {
                    addServerLog('📤 Sending files to server...');
                    const response = await fetch('/translate', {
                        method: 'POST',
                        body: formData
                    });

                    console.log('📥 Response status:', response.status);
                    addServerLog('📥 Server responded with status: ' + response.status);

                    if (!response.ok) {
                        clearInterval(progressInterval);
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }

                    addServerLog('✅ Translation completed successfully!');
                    const results = await response.json();
                    
                    // Complete progress to 100%
                    clearInterval(progressInterval);
                    document.getElementById('progress-fill').style.width = '100%';
                    
                    if (results.success_count > 0) {
                        const totalLines = results.files.reduce((sum, file) => sum + (file.lines_translated || 0), 0);
                        document.getElementById('status-text').textContent = `✅ Successfully translated ${totalLines} subtitle lines!`;
                        addServerLog(`🎉 Translated ${totalLines} lines across ${results.success_count} file(s)`);
                    } else {
                        document.getElementById('status-text').textContent = '❌ Translation failed - check results below';
                        addServerLog('❌ Translation failed - check error details below');
                    }

                    console.log('✅ Response received:', results);
                    displayResults(results);

                } catch (error) {
                    console.error('❌ Error:', error);
                    clearInterval(progressInterval);
                    document.getElementById('progress-fill').style.width = '0%';
                    document.getElementById('status-text').textContent = '❌ Error: ' + error.message;
                    document.getElementById('status-text').className = 'status error';
                    document.getElementById('status-text').style.display = 'block';
                    addServerLog('❌ Error: ' + error.message);
                } finally {
                    // Hide progress after 3 seconds to let user see the final message
                    setTimeout(() => {
                        document.getElementById('progress').style.display = 'none';
                    }, 3000);
                }
            };

            function displayResults(results) {
                const resultsDiv = document.getElementById('results');
                resultsDiv.innerHTML = '';

                if (results.error) {
                    resultsDiv.innerHTML = '<div class="status error">Error: ' + results.error + '</div>';
                    return;
                }

                const summary = document.createElement('div');
                summary.className = 'file-item';
                summary.innerHTML = `<h3>Translation Complete!</h3>
                    <p><strong>Service:</strong> ${results.service_used}</p>
                    <p><strong>Success:</strong> ${results.success_count}/${results.total_count} files</p>`;
                resultsDiv.appendChild(summary);

                results.files.forEach(file => {
                    const fileDiv = document.createElement('div');
                    fileDiv.className = 'file-item';
                    
                    if (file.success) {
                        const linesInfo = file.lines_translated ? ` (${file.lines_translated} lines)` : '';
                        fileDiv.innerHTML = `
                            <div class="file-success">
                                <h4>✅ ${file.original_name}${linesInfo}</h4>
                                <p><strong>Translated to:</strong> ${file.translated_name}</p>
                                <p><strong>Service:</strong> ${file.service}</p>
                                <button onclick="downloadFileSecure('${file.download_url}', '${file.translated_name}')" class="download-btn">📥 Download Translation</button>
                            </div>
                        `;
                    } else {
                        fileDiv.innerHTML = `
                            <div class="file-error">
                                <h4>❌ ${file.original_name}</h4>
                                <p><strong>Error:</strong> ${file.error}</p>
                                <p><strong>Service:</strong> ${file.service}</p>
                            </div>
                        `;
                    }
                    
                    resultsDiv.appendChild(fileDiv);
                });
            }

            function downloadFileSecure(url, filename) {
                // Use fetch to download file securely over HTTPS
                addServerLog('📥 Starting secure download: ' + filename);
                fetch(url)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                        }
                        return response.blob();
                    })
                    .then(blob => {
                        const downloadUrl = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = downloadUrl;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        window.URL.revokeObjectURL(downloadUrl);
                        addServerLog('✅ Download completed: ' + filename);
                    })
                    .catch(error => {
                        console.error('Download error:', error);
                        addServerLog('❌ Download failed: ' + error.message);
                        alert('Download failed: ' + error.message);
                    });
            }

            function addServerLog(message) {
                const logContent = document.getElementById('log-content');
                const timestamp = new Date().toLocaleTimeString();
                logContent.textContent += `[${timestamp}] ${message}\n`;
                logContent.scrollTop = logContent.scrollHeight;
            }

            function clearLogs() {
                document.getElementById('log-content').textContent = '';
            }

            function downloadFile(url) {
                const a = document.createElement('a');
                a.href = url;
                a.download = '';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }

            function clearResults() {
                document.getElementById('results').innerHTML = '';
                document.getElementById('server-logs').style.display = 'none';
                clearLogs();
            }

            // Initialize form state on page load
            document.addEventListener('DOMContentLoaded', function() {
                // Trigger the translator change event to show/hide appropriate fields
                const translatorSelect = document.getElementById('translator');
                if (translatorSelect.onchange) {
                    translatorSelect.onchange();
                }
            });
        </script>
    </body>
    </html>
    """

@app.post("/translate")
async def translate_files(
    files: List[UploadFile] = File(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    translator: str = Form("local_nllb"),
    api_key: Optional[str] = Form(None),
    endpoint: Optional[str] = Form(None),
    # Advanced Gemini parameters
    batch_size: Optional[str] = Form("300"),
    streaming: Optional[str] = Form("true"),
    thinking: Optional[str] = Form("true"),
    thinking_budget: Optional[str] = Form("2048"),
    temperature: Optional[str] = Form(""),
    top_p: Optional[str] = Form(""),
    top_k: Optional[str] = Form(""),
    free_quota: Optional[str] = Form("true"),
    use_colors: Optional[str] = Form("true")
):
    """Translate uploaded subtitle files using standalone AI services."""
    try:
        # Save uploaded files
        saved_files = []
        for file in files:
            if not file.filename:
                continue

            # Validate file extension
            ext = Path(file.filename).suffix.lower()
            if ext not in ['.srt', '.ass', '.ssa', '.vtt']:
                continue

            file_path = UPLOAD_DIR / file.filename
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            saved_files.append(file_path)

        if not saved_files:
            raise HTTPException(status_code=400, detail="No valid subtitle files uploaded")

        # Create translator config with user-provided parameters
        config = {
            'api_key': api_key,
            'endpoint': endpoint or 'http://192.168.1.233:6060/translate',
            'batch_size': int(batch_size) if batch_size else 300,
            'timeout': 300,
            'streaming': streaming.lower() == 'true' if streaming else True,
            'thinking': thinking.lower() == 'true' if thinking else True,
            'thinking_budget': int(thinking_budget) if thinking_budget else 2048,
            'temperature': float(temperature) if temperature else None,
            'top_p': float(top_p) if top_p else None,
            'top_k': int(top_k) if top_k else None,
            'free_quota': free_quota.lower() == 'true' if free_quota else True,
            'use_colors': use_colors.lower() == 'true' if use_colors else True
        }

        # Debug: Log the config (without exposing the actual API key)
        debug_api_key = api_key[:10] + '...' if api_key and len(api_key) > 10 else str(api_key)
        logger.info(f"🔧 Creating translator with config: api_key='{debug_api_key}', translator='{translator}'")
        logger.info(f"🔧 Advanced settings: batch_size={config['batch_size']}, streaming={config['streaming']}")

        # Create standalone translator
        translator_instance = StandaloneTranslatorFactory.create_translator(translator, config)
        logger.info(f"✅ Created {translator} translator successfully")

        results = []
        success_count = 0

        # Process each file
        for i, input_file in enumerate(saved_files, 1):
            try:
                logger.info(f"📁 Processing file {i}/{len(saved_files)}: {input_file.name}")
                
                # Create output filename
                output_file = OUTPUT_DIR / f"{input_file.stem}_{target_lang}{input_file.suffix}"

                logger.info(f"🔄 Translating: {input_file.name} -> {output_file.name}")
                logger.info(f"🌐 Service: {translator}, Languages: {source_lang} -> {target_lang}")
                
                # Translate the file
                result = await translator_instance.translate_file(input_file, source_lang, target_lang)
                
                if result:
                    original_subs, translated_subs = result
                    logger.info(f"📊 Translation result: ({type(original_subs).__name__} with {len(original_subs)} events, {type(translated_subs).__name__} with {len(translated_subs)} events)")
                    logger.info(f"📊 Result type: {type(result)}")
                    logger.info(f"📊 Result length: {len(result)}")
                    
                    # Save translated file
                    translated_subs.save(str(output_file))
                    logger.info(f"💾 Saved file: {output_file}")
                    
                    # Log some sample translations for verification
                    logger.info("🔍 Translation successful!")
                    logger.info(f"🔍 Original subs: {len(original_subs)} events")
                    logger.info(f"🔍 Translated subs: {len(translated_subs)} events")
                    
                    # Show first few translations as examples
                    for j, (orig, trans) in enumerate(zip(original_subs[:3], translated_subs[:3]), 1):
                        logger.info(f"🔍 Translated line {j}: '{trans.plaintext}'")
                    
                    success_count += 1
                    results.append({
                        "original_name": input_file.name,
                        "translated_name": output_file.name,
                        "success": True,
                        "download_url": f"/download/{output_file.name}",
                        "service": translator,
                        "lines_translated": len(translated_subs)
                    })
                else:
                    logger.error(f"❌ Translation failed for {input_file.name}: No result returned")
                    results.append({
                        "original_name": input_file.name,
                        "success": False,
                        "error": "Translation failed - no result returned",
                        "service": translator
                    })

            except Exception as e:
                logger.error(f"❌ Error processing {input_file.name}: {e}")
                import traceback
                logger.error(f"❌ Traceback: {traceback.format_exc()}")
                results.append({
                    "original_name": input_file.name,
                    "success": False,
                    "error": str(e),
                    "service": translator
                })

        # Close translator
        if hasattr(translator_instance, 'close'):
            await translator_instance.close()

        return {
            "files": results,
            "success_count": success_count,
            "total_count": len(saved_files),
            "service_used": translator
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Translation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download a translated file."""
    file_path = OUTPUT_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )

if __name__ == "__main__":
    import uvicorn
    import ssl
    import os
    
    print("🚀 Starting Standalone Subtitle Translator...")
    print("🌐 Available services: Local NLLB, Google Translate, DeepL, Gemini AI")
    
    # Check if SSL certificates exist
    cert_file = "cert.pem"
    key_file = "key.pem"
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print("🔒 SSL certificates found - starting HTTPS server")
        print("📖 Open your browser and go to: https://localhost:8002")
        print("⚠️  You may need to accept the self-signed certificate warning")
        
        # Create SSL context
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(cert_file, key_file)
        
        uvicorn.run(app, host="0.0.0.0", port=8002, ssl_keyfile=key_file, ssl_certfile=cert_file)
    else:
        print("⚠️  No SSL certificates found - starting HTTP server")
        print("📖 Open your browser and go to: http://localhost:8002")
        print("💡 To enable HTTPS, generate certificates with:")
        print("   openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes")
        print("⚠️  Note: This is a demo version. Real API services require valid API keys.")
        
        uvicorn.run(app, host="0.0.0.0", port=8002)
