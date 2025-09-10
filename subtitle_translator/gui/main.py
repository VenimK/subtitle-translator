"""Main GUI module for the subtitle translator."""
import time
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# Core Qt imports
from PyQt6.QtCore import (
    Qt, QSize, QThread, pyqtSignal, pyqtSlot, QObject, QTimer, QSettings, 
    QDateTime, QVariantAnimation, QCoreApplication, QEvent, QMimeData, QUrl
)
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QDragEnterEvent, QDropEvent, QStandardItemModel,
    QStandardItem, QTextCursor, QPixmap, QFontMetrics, QPalette, QColor,
    QGuiApplication, QFontDatabase, QPainter
)
from PyQt6.QtWidgets import (
    QTableView,
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QComboBox, QSpinBox, QLineEdit, QTextEdit,
    QProgressBar, QStatusBar, QSplitter, QToolBar, QMenuBar, QMenu,
    QMessageBox, QListWidget, QListWidgetItem, QStyle, QSizePolicy,
    QFrame, QDialog, QDialogButtonBox, QFormLayout, QCheckBox, QGroupBox,
    QTabWidget, QScrollArea, QStyleFactory, QStyleOption, QStylePainter,
    QStyledItemDelegate, QAbstractItemView, QToolButton, QSystemTrayIcon
)

from ..core import Translator, TranslationConfig, TranslationResult
from ..utils.config import ConfigManager
from .. import __version__

class QtLogHandler(logging.Handler, QObject):
    """A logging handler that emits a Qt signal."""
    log_updated = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__()
        QObject.__init__(self, parent)

    def emit(self, record):
        log_entry = self.format(record)
        self.log_updated.emit(log_entry, record.levelname.lower())

logger = logging.getLogger(__name__)

# High DPI scaling is now handled by Qt attributes

# Set the application style
def set_application_style(app):
    """Set the application style and palette."""
    # Use Fusion style for a more modern look
    app.setStyle(QStyleFactory.create('Fusion'))
    
    # Set a consistent font
    font = QFont()
    font.setFamily('Segoe UI' if sys.platform == 'win32' else 'Arial')
    font.setPointSize(10)
    app.setFont(font)
    
    # Set the application palette
    palette = app.palette()
    
    if True:  # Use dark theme by default for now
        # Dark theme colors
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        
        # Set disabled colors for dark theme
        disabled_color = QColor(127, 127, 127)
        dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_color)
        dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_color)
        dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_color)
        
        app.setPalette(dark_palette)
    else:
        # Light theme
        light_palette = QPalette()
        light_palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
        light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        light_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        light_palette.setColor(QPalette.ColorRole.Link, QColor(0, 102, 204))
        light_palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
        light_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        
        app.setPalette(light_palette)


class AsyncRunner(QObject):
    """Runs an async function in a separate thread's event loop."""
    started = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, coro, *args, **kwargs):
        super().__init__()
        self._coro = coro
        self._args = args
        self._kwargs = kwargs

    def run(self):
        """Run the coroutine."""
        self.started.emit()
        try:
            asyncio.run(self._coro(*self._args, **self._kwargs))
        finally:
            self.finished.emit()

class TranslationWorker(QObject):
    """Worker for handling translation in a separate thread."""
    
    # Signals
    progress_updated = pyqtSignal(int, int, str)  # current, total, status
    translation_complete = pyqtSignal(bool, str)   # success, message
    review_ready = pyqtSignal(object, object, object) # original_subs, translated_subs, output_path
    error_occurred = pyqtSignal(str)               # error message
    
    def __init__(self, translator: Translator, files: List[Path], output_dir: Path):
        """Initialize the translation worker."""
        super().__init__()
        self.translator = translator
        self.files = files
        self.output_dir = output_dir
        self._is_running = True
    
    def stop(self):
        """Stop the translation process."""
        self._is_running = False
        if self.translator and hasattr(self.translator, 'close'):
            if asyncio.iscoroutinefunction(self.translator.close):
                asyncio.run(self.translator.close())
            else:
                self.translator.close()


    async def run_translation(self):
        """Run the translation process."""
        total = len(self.files)
        success_count = 0
        
        logger.info(f"Starting translation of {total} files...")
        start_time = time.time()
        
        try:
            for i, input_file in enumerate(self.files, 1):
                if not self._is_running:
                    logger.warning("Translation cancelled by user.")
                    break
                
                file_start_time = time.time()
                self.progress_updated.emit(i, total, f"Translating {input_file.name}...")
                
                # Create output filename by removing any language code and adding target language
                import re
                stem = input_file.stem
                # Remove any existing language code (e.g., _eng, .eng, track2_eng, etc.)
                stem = re.sub(r'[._](eng|spa|nld|deu|fra|ita|por|rus|jpn|kor|zho|ara|tur|pol|ukr|swe|dan|nor|fin|hun|ces|ron|ell|bul|srp|hrv|slv|mkd|bos)(?:_[A-Za-z]{4,5})?$', '', stem)
                stem = re.sub(r'[._]track\d+[._](eng|spa|nld|deu|fra|ita|por|rus|jpn|kor|zho|ara|tur|pol|ukr|swe|dan|nor|fin|hun|ces|ron|ell|bul|srp|hrv|slv|mkd|bos)(?:_[A-Za-z]{4,5})?$', '', stem)
                # Add the target language code (first 3 chars of target_language, e.g., 'spa_Latn' -> 'spa')
                lang_code = self.translator.config.target_language[:3] if self.translator.config.target_language else 'trans'
                output_file = self.output_dir / f"{stem}_{lang_code}{input_file.suffix}"
                
                try:
                    translation_result = await self.translator.translate_file(
                        input_file,
                        source_language=self.translator.config.source_language,
                        target_language=self.translator.config.target_language
                    )

                    if translation_result:
                        original_subs, translated_subs = translation_result
                        self.review_ready.emit(original_subs, translated_subs, output_file)
                        success_count += 1
                        file_time = time.time() - file_start_time
                        logger.info(f"Successfully translated {input_file.name} in {file_time:.2f}s. Ready for review.")
                    else:
                        error_msg = f"Failed to translate {input_file.name}"
                        logger.error(error_msg)
                        self.error_occurred.emit(error_msg)
                
                except Exception as e:
                    error_msg = f"Error translating {input_file.name}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    self.error_occurred.emit(error_msg)
            
            total_time = time.time() - start_time
            if self._is_running:
                msg = f"Translation complete. {success_count}/{total} files processed in {total_time:.2f}s."
                if success_count == total:
                    logger.info(msg)
                else:
                    logger.warning(msg)
                self.translation_complete.emit(success_count > 0, msg)
            else:
                self.translation_complete.emit(False, "Translation cancelled.")
                
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            self.error_occurred.emit(f"Unexpected error: {str(e)}")
            self.translation_complete.emit(False, "Translation failed.")


class ReviewWindow(QDialog):
    """A dialog for reviewing and editing translations."""

    def __init__(self, original_subs, translated_subs, parent=None):
        super().__init__(parent)
        self.original_subs = original_subs
        self.translated_subs = translated_subs
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Review Translation")
        self.setMinimumSize(1000, 600)
        self.setLayout(QVBoxLayout())

        # Table view for side-by-side comparison
        self.table_view = QTableView()
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Original Text", "Translated Text"])
        self.table_view.setModel(self.model)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.layout().addWidget(self.table_view)

        # Populate the model
        for i in range(len(self.original_subs)):
            original_item = QStandardItem(self.original_subs[i].text)
            translated_item = QStandardItem(self.translated_subs[i].text)
            original_item.setFlags(original_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.model.appendRow([original_item, translated_item])

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout().addWidget(button_box)

    def get_edited_subs(self):
        """Return the subtitle object with edited text."""
        for i in range(self.model.rowCount()):
            self.translated_subs[i].text = self.model.item(i, 1).text()
        return self.translated_subs

class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self, config: ConfigManager):
        """Initialize the main window."""
        super().__init__()
        
        self.config = config
        self.settings = QSettings()
        self.translator = None

        # Set up logging
        self.log_handler = QtLogHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        self.log_handler.log_updated.connect(self.log)
        logging.getLogger().addHandler(self.log_handler)
        logging.getLogger().setLevel(logging.INFO)
        self.translation_worker = None
        self.translation_thread = None
        self.current_files = []
        self._is_busy = False
        
        # Animation for busy state
        self.busy_animation = QVariantAnimation(self)
        self.busy_animation.setStartValue(0)
        self.busy_animation.setEndValue(100)
        self.busy_animation.setDuration(1000)
        self.busy_animation.setLoopCount(-1)  # Infinite loop
        self.busy_animation.valueChanged.connect(self._update_busy_animation)
        
        self.init_ui()
        self.load_settings()
        self.init_translator()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(f"Subtitle Translator {__version__}")
        self.setMinimumSize(800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Add overlay for busy state
        self.overlay = QWidget(central_widget)
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        self.overlay.hide()
        self.overlay.setGeometry(0, 0, self.width(), self.height())
        
        # Add spinner for busy state
        self.spinner = QLabel(self.overlay)
        self.spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                background-color: rgba(50, 50, 50, 200);
                border-radius: 10px;
                padding: 20px;
            }
        """)
        self.spinner.hide()
        
        self.create_toolbar()
        
        content_splitter = QSplitter(Qt.Orientation.Vertical)
        
        file_group = QGroupBox("Files to Translate")
        file_layout = QVBoxLayout(file_group)
        
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.file_list.setAcceptDrops(True)
        self.file_list.setStyleSheet(
            """
            QListWidget {
                border: 2px dashed #666;
                border-radius: 5px;
                padding: 10px;
            }
            QListWidget::item {
                padding: 5px;
            }
            """
        )
        
        file_buttons = QHBoxLayout()
        self.add_files_btn = QPushButton("Add Files...")
        self.add_files_btn.clicked.connect(self.add_files)
        self.add_folder_btn = QPushButton("Add Folder...")
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.clear_files_btn = QPushButton("Clear All")
        self.clear_files_btn.clicked.connect(self.clear_files)
        file_buttons.addWidget(self.add_files_btn)
        file_buttons.addWidget(self.add_folder_btn)
        file_buttons.addStretch()
        file_buttons.addWidget(self.clear_files_btn)
        
        file_layout.addWidget(QLabel("Drag and drop files here or use the buttons below:"))
        file_layout.addWidget(self.file_list, 1)
        file_layout.addLayout(file_buttons)
        
        settings_group = QGroupBox("Translation Settings")
        settings_layout = QFormLayout(settings_group)
        
        self.translator_combo = QComboBox()
        # Add Local NLLB first as it's the default
        self.translator_combo.addItem("Local NLLB Server", "local_nllb")
        # Other translators
        self.translator_combo.addItem("Hugging Face API", "huggingface")
        self.translator_combo.addItem("Google Translate", "google")
        self.translator_combo.addItem("DeepL", "deepl")
        self.translator_combo.addItem("Gemini", "gemini")
        # Set Local NLLB as default
        self.translator_combo.setCurrentIndex(0)
        self.translator_combo.currentIndexChanged.connect(self.on_translator_changed)
        
        self.endpoint_edit = QLineEdit()
        self.endpoint_edit.setPlaceholderText("http://localhost:8080/translate")
        self.endpoint_edit.textChanged.connect(self.on_settings_changed)

        # Hugging Face Settings
        self.hf_settings = QWidget()
        hf_layout = QFormLayout(self.hf_settings)
        self.hf_api_key_edit = QLineEdit()
        self.hf_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.hf_api_key_edit.textChanged.connect(self.on_settings_changed)
        hf_layout.addRow("API Key:", self.hf_api_key_edit)

        # DeepL Settings
        self.deepl_settings = QWidget()
        deepl_layout = QFormLayout(self.deepl_settings)
        self.deepl_api_key_edit = QLineEdit()
        self.deepl_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepl_api_key_edit.textChanged.connect(self.on_settings_changed)
        deepl_layout.addRow("API Key:", self.deepl_api_key_edit)
        
        self.gemini_settings = QWidget()
        gemini_layout = QFormLayout(self.gemini_settings)
        self.gemini_api_key_edit = QLineEdit()
        self.gemini_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_api_key_edit.textChanged.connect(self.on_settings_changed)
        gemini_layout.addRow("API Key:", self.gemini_api_key_edit)

        self.gemini_prompt_edit = QTextEdit()
        self.gemini_prompt_edit.setPlaceholderText("Enter your custom prompt template here.")
        self.gemini_prompt_edit.textChanged.connect(self.on_settings_changed)
        gemini_layout.addRow("Prompt Template:", self.gemini_prompt_edit)

        self.gemini_tone_edit = QLineEdit()
        self.gemini_tone_edit.setPlaceholderText("e.g., formal, informal, humorous")
        gemini_layout.addRow("Tone:", self.gemini_tone_edit)
        self.gemini_tone_edit.textChanged.connect(self.on_settings_changed)
        
        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()
        self.populate_language_combos()
        
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 50)
        self.batch_size_spin.setValue(5)
        self.batch_size_spin.valueChanged.connect(self.on_settings_changed)
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(30, 3600)
        self.timeout_spin.setValue(300)
        self.timeout_spin.setSuffix(" seconds")
        self.timeout_spin.valueChanged.connect(self.on_settings_changed)
        
        settings_layout.addRow("Translator:", self.translator_combo)
        settings_layout.addRow("Endpoint:", self.endpoint_edit)
        settings_layout.addRow("Hugging Face Settings:", self.hf_settings)
        settings_layout.addRow("DeepL Settings:", self.deepl_settings)
        settings_layout.addRow("Gemini Settings:", self.gemini_settings)
        settings_layout.addRow("Source Language:", self.source_lang_combo)
        settings_layout.addRow("Target Language:", self.target_lang_combo)
        settings_layout.addRow("Batch Size:", self.batch_size_spin)
        settings_layout.addRow("Timeout:", self.timeout_spin)
        
        output_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(self.output_dir_edit, 1)
        output_layout.addWidget(browse_btn)
        settings_layout.addRow("Output Directory:", output_layout)
        
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.status_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        monospace_font = QFont('Menlo' if sys.platform == 'darwin' else 'Courier New')
        monospace_font.setStyleHint(QFont.StyleHint.Monospace)
        self.log_edit.setFont(monospace_font)
        
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(QLabel("Log:"))
        progress_layout.addWidget(self.log_edit, 1)
        
        content_splitter.addWidget(file_group)
        content_splitter.addWidget(settings_group)
        content_splitter.addWidget(progress_group)
        content_splitter.setSizes([300, 200, 200])
        
        main_layout.addWidget(content_splitter, 1)
        
        self.translate_btn = QPushButton("Translate")
        self.translate_btn.clicked.connect(self.start_translation)
        self.translate_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2a82da;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:disabled {
                background-color: #666;
            }
            QPushButton:hover {
                background-color: #3a92ea;
            }
            QPushButton:pressed {
                background-color: #1a72ca;
            }
            """
        )
        main_layout.addWidget(self.translate_btn)
        
        self.statusBar().showMessage("Ready")
        self.setAcceptDrops(True)
        self.on_translator_changed()

    @pyqtSlot(str, str)
    def log(self, message: str, level: str = 'info'):
        """Log a message to the log widget."""
        color_map = {
            'debug': 'gray',
            'info': 'white',
            'warning': 'orange',
            'error': 'red',
            'critical': 'red',
        }
        color = color_map.get(level, 'white')
        log_entry = f'<font color="{color}">{message}</font>'
        self.log_edit.append(log_entry)
    
    def create_toolbar(self):
        """Create the application toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        file_menu = self.menuBar().addMenu("&File")
        
        open_action = QAction("&Open Files...", self)
        open_action.triggered.connect(self.add_files)
        open_action.setShortcut("Ctrl+O")
        file_menu.addAction(open_action)
        
        open_folder_action = QAction("Open &Folder...", self)
        open_folder_action.triggered.connect(self.add_folder)
        open_folder_action.setShortcut("Ctrl+Shift+O")
        file_menu.addAction(open_folder_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut("Ctrl+Q")
        file_menu.addAction(exit_action)
        
        edit_menu = self.menuBar().addMenu("&Edit")
        
        settings_action = QAction("&Preferences...", self)
        settings_action.triggered.connect(self.show_preferences)
        settings_action.setShortcut("Ctrl+,")
        edit_menu.addAction(settings_action)
        
        view_menu = self.menuBar().addMenu("&View")
        
        toggle_toolbar_action = QAction("&Toolbar", self, checkable=True)
        toggle_toolbar_action.setChecked(True)
        toggle_toolbar_action.triggered.connect(
            lambda: self.toolBar().setVisible(toggle_toolbar_action.isChecked())
        )
        view_menu.addAction(toggle_toolbar_action)
        
        help_menu = self.menuBar().addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        toolbar.addAction(open_action)
        toolbar.addAction(open_folder_action)
        toolbar.addSeparator()
        toolbar.addAction(settings_action)
    
    def populate_language_combos(self):
        """Populate the language combo boxes."""
        languages = self.config.get_available_languages()
        
        self.source_lang_combo.clear()
        self.target_lang_combo.clear()
        
        for code, name in languages.items():
            self.source_lang_combo.addItem(f"{name} ({code})", code)
            self.target_lang_combo.addItem(f"{name} ({code})", code)
        
        source_lang = self.config.get('languages.source', 'eng_Latn')
        target_lang = self.config.get('languages.target', 'nld_Latn')
        
        source_index = self.source_lang_combo.findData(source_lang)
        if source_index >= 0:
            self.source_lang_combo.setCurrentIndex(source_index)
        
        target_index = self.target_lang_combo.findData(target_lang)
        if target_index >= 0:
            self.target_lang_combo.setCurrentIndex(target_index)
        
        self.source_lang_combo.currentIndexChanged.connect(self.on_settings_changed)
        self.target_lang_combo.currentIndexChanged.connect(self.on_settings_changed)
    
    def load_settings(self):
        """Load settings from config."""
        # Always start with Local NLLB
        index = self.translator_combo.findData('local_nllb')
        if index >= 0:
            self.translator_combo.setCurrentIndex(index)
        
        self.endpoint_edit.setText(self.config.get('translator.endpoint', 'http://localhost:8080/translate'))
        self.hf_api_key_edit.setText(self.settings.value("huggingface/api_key", ""))
        self.deepl_api_key_edit.setText(self.settings.value("deepl/api_key", ""))
        self.gemini_api_key_edit.setText(self.settings.value("gemini/api_key", ""))
        self.gemini_prompt_edit.setText(self.settings.value("gemini/prompt_template", ""))
        self.gemini_tone_edit.setText(self.settings.value("gemini/tone", ""))
        self.batch_size_spin.setValue(self.config.get('translator.batch_size', 5))
        self.timeout_spin.setValue(self.config.get('translator.timeout', 300))
        
        output_dir = self.config.get('directories.save_location', str(Path.home() / 'Documents' / 'Translated Subtitles'))
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        self.output_dir_edit.setText(output_dir)
        
        geometry = self.config.get('ui.window_geometry')
        if geometry:
            self.restoreGeometry(geometry)
        
        splitter_state = self.config.get('ui.splitter_state')
        if splitter_state:
            self.centralWidget().findChild(QSplitter).restoreState(splitter_state)
    def save_settings(self):
        """Save settings to config."""
        self.config.set('translator.type', self.translator_combo.currentData())
        self.config.set('translator.endpoint', self.endpoint_edit.text())
        self.settings.setValue("huggingface/api_key", self.hf_api_key_edit.text())
        self.settings.setValue("deepl/api_key", self.deepl_api_key_edit.text())
        self.settings.setValue("gemini/api_key", self.gemini_api_key_edit.text())
        self.settings.setValue("gemini/prompt_template", self.gemini_prompt_edit.toPlainText())
        self.settings.setValue("gemini/tone", self.gemini_tone_edit.text())
        self.config.set('translator.batch_size', self.batch_size_spin.value())
        self.config.set('translator.timeout', self.timeout_spin.value())
        self.config.set('languages.source', self.source_lang_combo.currentData())
        self.config.set('languages.target', self.target_lang_combo.currentData())
        self.config.set('directories.save_location', self.output_dir_edit.text())
        self.config.set('ui.window_geometry', self.saveGeometry())
        
        splitter = self.centralWidget().findChild(QSplitter)
        if splitter:
            self.config.set('ui.splitter_state', splitter.saveState())
        
        self.config.save()
    
    def set_busy(self, busy: bool, message: str = "Processing..."):
        """Set the application's busy state."""
        self._is_busy = busy
        self.setEnabled(not busy)
        
        if busy:
            self.overlay.raise_()
            self.overlay.show()
            self.spinner.setText(message)
            self.spinner.show()
            self.busy_animation.start()
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            self.overlay.hide()
            self.spinner.hide()
            self.busy_animation.stop()
            QApplication.restoreOverrideCursor()
    
    def _update_busy_animation(self, value):
        """Update the busy animation."""
        if not self._is_busy:
            return
            
        # Update spinner text with ellipsis animation
        text = self.spinner.text().strip('.')
        dots = '.' * ((value // 20) % 4)
        self.spinner.setText(f"{text}{dots}")
        
        # Update overlay size if window was resized
        self.overlay.setGeometry(0, 0, self.width(), self.height())
        self.spinner.move(
            (self.width() - self.spinner.width()) // 2,
            (self.height() - self.spinner.height()) // 2
        )
    
    def init_translator(self):
        """Initialize the translator with current settings."""
        try:
            translator_type = self.translator_combo.currentData()
            api_key = ""
            if translator_type == 'huggingface':
                api_key = self.hf_api_key_edit.text()
            elif translator_type == 'deepl':
                api_key = self.deepl_api_key_edit.text()
            elif translator_type == 'gemini':
                api_key = self.gemini_api_key_edit.text()
            elif translator_type == 'google':
                api_key = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')

            config = TranslationConfig(
                translator_type=translator_type,
                endpoint=self.endpoint_edit.text(),
                api_key=api_key,
                gemini_prompt_template=self.gemini_prompt_edit.toPlainText(),
                gemini_tone=self.gemini_tone_edit.text(),
                batch_size=self.batch_size_spin.value(),
                source_language=self.source_lang_combo.currentData(),
                target_language=self.target_lang_combo.currentData(),
                timeout=self.timeout_spin.value()
            )
            self.translator = Translator(config)
        except Exception as e:
            self.log(f"Failed to initialize translator: {e}", 'error')
            QMessageBox.critical(self, "Translator Error", f"Failed to initialize translator: {str(e)}")
    
    def on_translator_changed(self):
        """Handle translator type change."""
        translator_type = self.translator_combo.currentData()
        is_local = (translator_type == 'local_nllb')
        is_hf = (translator_type == 'huggingface')
        is_deepl = (translator_type == 'deepl')
        is_gemini = (translator_type == 'gemini')

        self.endpoint_edit.setVisible(is_local)
        self.hf_settings.setVisible(is_hf)
        self.deepl_settings.setVisible(is_deepl)
        self.gemini_settings.setVisible(is_gemini)
        self.init_translator()
    
    def on_settings_changed(self):
        """Handle settings changes."""
        self.init_translator()
    
    def add_files(self):
        """Add files to the translation list."""
        files, _ = QFileDialog.getOpenFileNames(self, "Select Subtitle Files", "", "Subtitle Files (*.srt *.ass *.ssa *.vtt)")
        if files:
            self.add_file_paths(files)
    
    def add_folder(self):
        """Add all subtitle files from a folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            files = []
            for ext in ('*.srt', '*.ass', '*.ssa', '*.vtt'):
                files.extend(Path(folder).rglob(ext))
            self.add_file_paths([str(f) for f in files])
    
    def add_file_paths(self, file_paths: List[str]):
        """Add multiple file paths to the list."""
        current_files = {self.file_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.file_list.count())}
        added_count = 0
        for file_path in file_paths:
            if file_path not in current_files:
                item = QListWidgetItem(Path(file_path).name)
                item.setData(Qt.ItemDataRole.UserRole, file_path)
                item.setToolTip(file_path)
                self.file_list.addItem(item)
                added_count += 1
        if added_count > 0:
            self.statusBar().showMessage(f"Added {added_count} file(s).", 3000)
    
    def clear_files(self):
        """Clear the file list."""
        if self.file_list.count() > 0:
            if QMessageBox.question(self, "Clear Files", "Are you sure?") == QMessageBox.StandardButton.Yes:
                self.file_list.clear()
    
    def browse_output_dir(self):
        """Browse for output directory."""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir_edit.setText(directory)
    
    def start_translation(self):
        """Start the translation process."""
        if self._is_busy:
            return
            
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "No Files", "Please add files to translate.")
            return
        
        output_dir = Path(self.output_dir_edit.text())
        if not output_dir.is_dir():
            QMessageBox.warning(self, "Invalid Directory", "Please select a valid output directory.")
            return
        
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot create output directory: {e}")
            return
        
        self.save_settings()
        
        files = [Path(self.file_list.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(self.file_list.count())]
        
        # Clear previous state
        self.progress_bar.setValue(0)
        self.log_edit.clear()
        
        # Set up worker and thread
        self.translation_worker = TranslationWorker(self.translator, files, output_dir)
        self.translation_thread = QThread()
        self.translation_worker.moveToThread(self.translation_thread)
        
        # Connect signals
        self.translation_worker.progress_updated.connect(self.on_translation_progress)
        self.translation_worker.translation_complete.connect(self.on_translation_complete)
        self.translation_worker.review_ready.connect(self.show_review_window)
        self.translation_worker.error_occurred.connect(self.on_translation_error)
        
        # Create a runner for the async task
        self.async_runner = AsyncRunner(self.translation_worker.run_translation)
        self.async_runner.moveToThread(self.translation_thread)

        # Connect thread events
        self.translation_thread.started.connect(self.async_runner.run)
        self.async_runner.finished.connect(self.cleanup_translation)
        self.translation_thread.finished.connect(self.translation_thread.deleteLater)
        
        # Set up cancellation
        self.cancel_requested = False
        self.translate_btn.setText("Cancel")
        self.translate_btn.clicked.disconnect()
        self.translate_btn.clicked.connect(self.cancel_translation)
        
        # Show busy state
        self.set_busy(True, "Working on translation...")
        
        # Start the thread
        self.translation_thread.start()
    

    def on_translation_progress(self, current: int, total: int, status: str):
        """Handle translation progress."""
        try:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            
            # Update status with progress percentage
            if total > 0:
                percent = int((current / total) * 100)
                status = f"{status} ({percent}%)"
            
            self.status_label.setText(status)
            
            # Process events to keep UI responsive
            QApplication.processEvents()
            
        except Exception as e:
            self.log(f"Error updating progress: {e}", 'error')
    
    def cancel_translation(self):
        """Cancel the current translation process."""
        if not self._is_busy:
            return
            
        if QMessageBox.question(
            self, 
            "Cancel Translation", 
            "Are you sure you want to cancel the current translation?"
        ) == QMessageBox.StandardButton.Yes:
            self.cancel_requested = True
            if self.translation_worker:
                self.translation_worker.stop()
            self.cleanup_translation()
            self.log("Translation cancelled by user.", 'warning')
            self.status_label.setText("Translation cancelled")
    
    def cleanup_translation(self):
        """Clean up after translation is complete or cancelled."""
        # Reset UI
        self.translate_btn.setText("Translate")
        self.translate_btn.clicked.disconnect()
        self.translate_btn.clicked.connect(self.start_translation)
        
        # Clean up thread and worker
        if self.translation_thread:
            if self.translation_thread.isRunning():
                self.translation_thread.quit()
                self.translation_thread.wait(2000)  # Wait up to 2 seconds
            self.translation_thread = None
        
        self.translation_worker = None
        self.set_busy(False)
    
    def on_translation_complete(self, success: bool, message: str):
        """Handle translation completion."""
        try:
            self.status_label.setText("Ready" if success else "Translation completed with errors")
            
            if success:
                self.progress_bar.setValue(self.progress_bar.maximum())
                self.log("Translation completed successfully!", 'success')
            else:
                self.log(f"Translation completed with errors: {message}", 'error')
            
            if not self.cancel_requested:
                QMessageBox.information(
                    self, 
                    "Translation Complete", 
                    message,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok
                )
        except Exception as e:
            self.log(f"Error in completion handler: {e}", 'error')
        finally:
            self.cleanup_translation()
    
    @pyqtSlot(str)
    def on_translation_error(self, error: str):
        """Handle translation errors."""
        self.log(error, 'error')

    def show_review_window(self, original_subs, translated_subs, output_path):
        """Show the review window for a translated file."""
        review_window = ReviewWindow(original_subs, translated_subs, self)
        if review_window.exec():
            edited_subs = review_window.get_edited_subs()
            try:
                edited_subs.save(str(output_path))
                self.log(f"Saved reviewed translation to {output_path.name}", 'success')
            except Exception as e:
                self.log(f"Failed to save reviewed translation: {e}", 'error')
                QMessageBox.critical(self, "Save Error", f"Failed to save file: {e}")

    @pyqtSlot(str, str)
    def log(self, message: str, level: str = 'info'):
        """Add a message to the log."""
        color = {
            'info': '#FFFFFF',
            'warning': '#FFA500',
            'error': '#FF4500'
        }.get(level, '#FFFFFF')
        
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        
        cursor = self.log_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(f'<span style="color: #888;">[{timestamp}]</span> <span style="color: {color};">{message}</span><br>')
        self.log_edit.ensureCursorVisible()

    def show_preferences(self):
        """Show the preferences dialog."""
        QMessageBox.information(self, "Preferences", "Not implemented yet.")
    
    def show_about(self):
        """Show the about dialog."""
        QMessageBox.about(self, "About", f"Subtitle Translator v{__version__}")
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.translation_thread and self.translation_thread.isRunning():
            if QMessageBox.question(self, "Confirm Exit", "Translation in progress. Quit?") == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self.translation_worker.stop()
            self.translation_thread.quit()
            self.translation_thread.wait()
        
        self.save_settings()
        event.accept()
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event."""
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self.add_file_paths(files)
        
    def resizeEvent(self, event):
        """Handle window resize event."""
        super().resizeEvent(event)
        # Update overlay and spinner positions when window is resized
        if hasattr(self, 'overlay') and hasattr(self, 'spinner'):
            self.overlay.setGeometry(0, 0, self.width(), self.height())
            self.spinner.move(
                (self.width() - self.spinner.width()) // 2,
                (self.height() - self.spinner.height()) // 2
            )


def main():
    """Main entry point for the GUI application."""
    # Set high DPI settings before creating the application
    if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    
    # Enable high DPI scaling
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('subtitle_translator.log')
        ]
    )
    
    # Create application
    app = QApplication(sys.argv)
    
    app.setApplicationName("Subtitle Translator")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("YourOrg")
    
    set_application_style(app)
    
    config = ConfigManager()
    window = MainWindow(config)
    window.show()
    
    if len(sys.argv) > 1:
        window.add_file_paths(sys.argv[1:])
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()