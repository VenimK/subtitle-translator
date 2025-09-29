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
    """Gemini AI translator for standalone usage."""

    async def _translate_batch(self, texts, source_language, target_language):
        """Translate using Gemini AI."""
        logger.info(f"Gemini: Translating {len(texts)} texts from {source_language} to {target_language}")
        
        # For demo purposes, simulate translation
        translated_texts = []
        for text in texts:
            # Simple demo transformation
            translated_text = f"[GEMINI DEMO] {text}"
            translated_texts.append(translated_text)
            logger.info(f"Gemini: '{text}' -> '{translated_text}'")
        
        return translated_texts

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
                margin-bottom: 30px;
                font-weight: bold;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
                color: #555;
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
                <strong>Note:</strong> This is a demo version. API services require valid API keys and internet connection.
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

            <div id="results" class="file-list"></div>
        </div>

        <script>
            // Show/hide endpoint field based on translator selection
            document.getElementById('translator').onchange = function() {
                const endpointGroup = document.getElementById('endpoint-group');
                const apiKeyField = document.getElementById('api_key').closest('.form-group');
                
                if (this.value === 'local_nllb') {
                    endpointGroup.style.display = 'block';
                    apiKeyField.style.display = 'none';
                } else {
                    endpointGroup.style.display = 'none';
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

                console.log('🌐 Source language:', sourceLang);
                console.log('🌐 Target language:', targetLang);
                console.log('🤖 Translator:', translator);
                console.log('🔑 API Key:', apiKey ? '***provided***' : 'not provided');
                console.log('🔗 Endpoint:', endpoint);

                formData.append('source_lang', sourceLang);
                formData.append('target_lang', targetLang);
                formData.append('translator', translator);
                formData.append('api_key', apiKey);
                formData.append('endpoint', endpoint);

                // Show progress
                document.getElementById('progress').style.display = 'block';
                document.getElementById('progress-fill').style.width = '0%';
                document.getElementById('status-text').textContent = '🚀 Initializing translation service...';

                console.log('📤 Sending request to /translate...');

                try {
                    const response = await fetch('/translate', {
                        method: 'POST',
                        body: formData
                    });

                    console.log('📥 Response status:', response.status);

                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }

                    const results = await response.json();
                    console.log('✅ Response received:', results);
                    displayResults(results);

                } catch (error) {
                    console.error('❌ Error:', error);
                    document.getElementById('status-text').textContent = '❌ Error: ' + error.message;
                    document.getElementById('status-text').className = 'status error';
                    document.getElementById('status-text').style.display = 'block';
                } finally {
                    document.getElementById('progress').style.display = 'none';
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
                        fileDiv.innerHTML = `
                            <strong>${file.original_name}</strong> → <strong>${file.translated_name}</strong>
                            <button class="download-btn" onclick="downloadFile('${file.download_url}')">Download</button>
                        `;
                    } else {
                        fileDiv.innerHTML = `
                            <strong>${file.original_name}</strong> - Error: ${file.error}
                        `;
                        fileDiv.style.borderLeftColor = '#dc3545';
                    }

                    resultsDiv.appendChild(fileDiv);
                });
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
            }
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
    endpoint: Optional[str] = Form(None)
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

        # Create translator config
        config = {
            'api_key': api_key,
            'endpoint': endpoint or 'http://192.168.1.233:6060/translate',
            'batch_size': 5,
            'timeout': 300
        }

        # Create standalone translator
        translator_instance = StandaloneTranslatorFactory.create_translator(translator, config)
        logger.info(f"Created {translator} translator successfully")

        results = []
        success_count = 0

        # Process each file
        for input_file in saved_files:
            try:
                # Create output filename
                output_file = OUTPUT_DIR / f"{input_file.stem}_{target_lang}{input_file.suffix}"

                logger.info(f"Translating: {input_file} -> {output_file}")
                logger.info(f"Service: {translator}, Languages: {source_lang} -> {target_lang}")

                # Perform translation
                result = await translator_instance.translate_file(
                    input_file,
                    source_language=source_lang,
                    target_language=target_lang
                )

                logger.info(f"Translation result: {result}")
                logger.info(f"Result type: {type(result)}")
                logger.info(f"Result length: {len(result) if result else 'None'}")

                if result and len(result) == 2:
                    original_subs, translated_subs = result

                    print(f"🔍 Translation successful!")
                    print(f"🔍 Original subs: {len(original_subs)} events")
                    print(f"🔍 Translated subs: {len(translated_subs)} events")
                    
                    # Check first few translated lines
                    for i, event in enumerate(translated_subs[:3]):
                        print(f"🔍 Translated line {i+1}: {repr(event.plaintext)}")

                    # Save the translated subtitles to output file
                    translated_subs.save(str(output_file))
                    print(f"🔍 Saved file: {output_file}")

                    results.append({
                        "original_name": input_file.name,
                        "translated_name": output_file.name,
                        "success": True,
                        "download_url": f"/download/{output_file.name}",
                        "service": translator
                    })
                    success_count += 1
                else:
                    error_msg = "Translation failed - no result returned"
                    print(f"🔍 Translation failed: {error_msg}")
                    print(f"🔍 Result: {result}")
                    logger.error(f"Translation failed for {input_file}: {error_msg}")
                    results.append({
                        "original_name": input_file.name,
                        "success": False,
                        "error": error_msg,
                        "service": translator
                    })

            except Exception as e:
                logger.error(f"Error processing {input_file}: {e}")
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
    print("🚀 Starting Standalone Subtitle Translator...")
    print("🌐 Available services: Local NLLB, Google Translate, DeepL, Gemini AI")
    print("📖 Open your browser and go to: http://localhost:8002")
    print("⚠️  Note: This is a demo version. Real API services require valid API keys.")
    uvicorn.run(app, host="0.0.0.0", port=8002)
