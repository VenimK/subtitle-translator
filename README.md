# Subtitle Translator

A powerful and flexible subtitle translation tool that supports multiple translation backends, including local NLLB server and Hugging Face Inference API.

## Features

- Translate subtitle files between multiple languages
- Support for SRT format
- Multiple translation backends:
  - DeepL
  - Google Gemini
  - Google Cloud Translate
  - Hugging Face Inference API
  - Local NLLB Server
- Command-line interface (CLI)
- Graphical User Interface (GUI)
- Batch processing of multiple files
- Progress tracking

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/VenimK/subtitle-translator.git
   cd subtitle-translator
   ```

2. Install the package in development mode:
   ```bash
   pip install -e .
   ```

   Or install with GUI support:
   ```bash
   pip install -e ".[gui]"
   ```

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

After installation, you can launch the GUI with:

```bash
subtitle-translator-gui
```

Or if you're in development mode:
```bash
python -m subtitle_translator.gui.main
```

## Configuration

Create a `config.json` file in your home directory (`~/.config/subtitle_translator/`) with the following structure:

```json
{
    "translator_type": "local_nllb",
    "endpoint": "http://localhost:6060",
    "api_key": "your_api_key_here",
    "batch_size": 5,
    "source_language": "eng_Latn",
    "target_language": "spa_Latn"
}
```

## Development

1. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

2. Run tests:
   ```bash
   pytest
   ```

3. Format code:
   ```bash
   black .
   isort .
   ```

## License

MIT
