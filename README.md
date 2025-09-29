# Subtitle Translator

A powerful and flexible subtitle translation tool that supports multiple translation backends, including local NLLB server, cloud APIs, and a standalone web interface.

## Features

- **Multiple Format Support**: SRT, ASS, SSA, VTT subtitle formats
- **Multiple Translation Backends**:
  - **Local NLLB Server** - Self-hosted translation using Facebook's NLLB model
  - **Google Translate API** - Cloud-based translation service
  - **DeepL API** - High-quality translation service
  - **Google Gemini AI** - Advanced AI translation
- **Multiple Interfaces**:
  - Command-line interface (CLI)
  - Graphical User Interface (GUI) with PyQt6
  - Standalone Web Interface (FastAPI)
- **Batch Processing**: Handle multiple files simultaneously
- **Progress Tracking**: Real-time progress updates
- **Configurable Settings**: Customizable translation parameters

## System Requirements

- **Python**: 3.8 or higher
- **Operating System**: Windows, macOS, or Linux
- **RAM**: 4GB minimum (8GB recommended for large files)
- **Storage**: 500MB free space for dependencies
- **Network**: Internet connection required for cloud APIs

## Installation

### Method 1: Standard Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/VenimK/subtitle-translator.git
   cd subtitle-translator
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install fastapi uvicorn aiohttp langdetect pysubs2 google-cloud-translate deepl google-generativeai
   ```

4. **Install the package**:
   ```bash
   pip install -e .
   ```

### Method 2: GUI Installation (with PyQt6)

For GUI support, install with:
```bash
pip install -e ".[gui]"
```

### Method 3: Development Installation

For development with all optional dependencies:
```bash
pip install -e ".[dev]"
```

## Quick Start

### Standalone Web Interface (Recommended)

The easiest way to get started is using the standalone web interface:

1. **Start the web server**:
   ```bash
   cd /path/to/subtitle-translator
   source venv/bin/activate  # Activate virtual environment if using one
   python web_app_standalone.py
   ```

2. **Open your browser** and go to: `http://localhost:8002`

3. **Upload subtitle files** and select your translation service

**Available Services in Web Interface**:
- **Local NLLB Server**: Connects to your self-hosted NLLB translation server
- **Google Translate**: Requires Google Cloud API key
- **DeepL**: Requires DeepL API key
- **Gemini AI**: Requires Google AI API key

### Local NLLB Server Setup (Optional)

For the best translation quality, you can set up your own NLLB server:

1. **Install Docker** on your system

2. **Run the NLLB container**:
   ```bash
   docker run -p 6060:6060 ghcr.io/venimk/nllb-api:latest
   ```

3. **Update endpoint** in the web interface: `http://localhost:6060/translate`

## Usage

### Command Line Interface (CLI)

```bash
# Translate a single file
subtitle-translator translate input.srt --source-lang eng --target-lang spa

# Translate all SRT files in a directory
subtitle-translator translate /path/to/subtitles/ --source-lang eng --target-lang spa --output-dir /output/path/

# Use local NLLB server
subtitle-translator translate input.srt --source-lang eng --target-lang spa --backend local_nllb --endpoint http://localhost:6060
```

### Graphical User Interface (GUI)

```bash
# Launch GUI
subtitle-translator-gui

# Or run directly
python -m subtitle_translator.gui.main
```

### Web Interface

```bash
# Start web server
python web_app_standalone.py

# Access at http://localhost:8002
```

## Configuration

### API Keys Setup

For cloud translation services, you'll need API keys:

1. **Google Translate**: Get key from [Google Cloud Console](https://console.cloud.google.com/)
2. **DeepL**: Get key from [DeepL API](https://www.deepl.com/pro-api)
3. **Google Gemini**: Get key from [Google AI Studio](https://makersuite.google.com/app/apikey)

### Configuration File

Create a `config.json` file in `~/.config/subtitle_translator/`:

```json
{
  "translator_type": "local_nllb",
  "endpoint": "http://localhost:6060/translate",
  "api_key": "your_api_key_here",
  "batch_size": 5,
  "source_language": "eng_Latn",
  "target_language": "spa_Latn"
}
```

### Language Codes

Use these language codes for translation:

| Language | Code | Language | Code |
|----------|------|----------|------|
| English | `eng_Latn` | Spanish | `spa_Latn` |
| French | `fra_Latn` | German | `deu_Latn` |
| Italian | `ita_Latn` | Portuguese | `por_Latn` |
| Russian | `rus_Cyrl` | Japanese | `jpn_Jpan` |
| Korean | `kor_Hang` | Chinese | `zho_HANS` |
| Arabic | `ara_Arab` | Dutch | `nld_Latn` |

## Supported File Formats

- **SRT** (.srt) - SubRip subtitle format
- **ASS** (.ass) - Advanced SubStation Alpha
- **SSA** (.ssa) - SubStation Alpha
- **VTT** (.vtt) - WebVTT format

## Troubleshooting

### Common Issues

1. **Port 8002 already in use**:
   ```bash
   # Kill existing process
   lsof -ti:8002 | xargs kill
   ```

2. **Module not found errors**:
   - Ensure virtual environment is activated
   - Check Python version (3.8+)
   - Reinstall dependencies

3. **NLLB server connection failed**:
   - Verify Docker container is running
   - Check firewall settings
   - Ensure port 6060 is accessible

4. **API key errors**:
   - Verify API keys are correct
   - Check API quotas and billing
   - Ensure network connectivity

### Getting Help

- Check the [Issues](https://github.com/VenimK/subtitle-translator/issues) page
- Create a new issue with detailed error messages
- Include your system information (OS, Python version)

## Development

### Setting up Development Environment

1. **Install development dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

2. **Run tests**:
   ```bash
   pytest
   ```

3. **Format code**:
   ```bash
   black .
   isort .
   ```

4. **Type checking**:
   ```bash
   mypy .
   ```

### Project Structure

```
subtitle-translator/
├── subtitle_translator/          # Main package
│   ├── translators/              # Translation backends
│   ├── gui/                      # GUI components
│   └── cli/                      # Command-line interface
├── web_app_standalone.py         # Standalone web interface
├── pyproject.toml               # Project configuration
└── README.md                    # This file
```

## Performance Tips

- **For large files**: Use Local NLLB server (best quality)
- **For speed**: Use Google Translate or DeepL
- **Batch processing**: Process multiple files together for efficiency
- **Memory usage**: Close other applications when processing large files

## License

MIT

---

**Made with ❤️ for subtitle translation enthusiasts**
