"""Subtitle Translator - A powerful tool for translating subtitle files."""

from pathlib import Path

# Version of the package
__version__ = "0.1.0"

# Package root directory
PACKAGE_ROOT = Path(__file__).parent

# Data directory for language models and other assets
DATA_DIR = PACKAGE_ROOT / "data"

# UI directory for Qt UI files
UI_DIR = PACKAGE_ROOT / "ui"

# Icons directory
ICONS_DIR = PACKAGE_ROOT / "icons"

# Ensure directories exist
for directory in [DATA_DIR, UI_DIR, ICONS_DIR]:
    directory.mkdir(exist_ok=True)

# Import core functionality
from .core.translator import Translator, TranslationConfig
from .gui.main import main as gui_main
from .cli.main import main as cli_main

__all__ = [
    'Translator',
    'TranslationConfig',
    'gui_main',
    'cli_main',
    '__version__',
]
