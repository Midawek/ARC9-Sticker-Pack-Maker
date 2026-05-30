import sys
import os
import ctypes
import threading
import queue
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

# --- Determine the base path for bundled assets and modules ---
if getattr(sys, 'frozen', False):
    BASE_PATH = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    OUTPUT_BASE_PATH = Path(sys.executable).parent
else:
    BASE_PATH = Path(__file__).resolve().parents[2]
    OUTPUT_BASE_PATH = BASE_PATH

# --- Consolidate sys.path modification here ---
for dependency_path in (
    BASE_PATH / "vendor" / "libs",
    BASE_PATH / "vendor" / "vtflib_wrapper" / "src",
):
    dependency_path_str = str(dependency_path)
    if dependency_path_str not in sys.path:
        sys.path.insert(0, dependency_path_str)

# --- Dependency Management ---
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox,
        QStackedWidget, QFrame, QCheckBox, QProgressBar, QGraphicsOpacityEffect,
        QListWidget, QListWidgetItem, QSplitter, QComboBox, QScrollArea,
        QTreeWidget, QTreeWidgetItem)
    from PySide6.QtGui import QPixmap, QFontDatabase, QFont, QMovie, QIcon, QColor, QPainter, QDesktopServices, QPainterPath
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtCore import Qt, QThread, Signal, QObject, QPropertyAnimation, QEasingCurve, Property, QSequentialAnimationGroup, QPoint, QSettings, QUrl, QSize, QParallelAnimationGroup
except ImportError:
    print("ERROR: PySide6 is not installed. Please install it using: pip install PySide6")
    sys.exit(1)


try:
    from arc9_sticker_pack_maker import __version__ as APP_VERSION
    from arc9_sticker_pack_maker import core
except ImportError as e:
    # Use QMessageBox if QApplication has been successfully imported and initialized
    if 'QApplication' in locals() or 'QApplication' in globals():
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        QMessageBox.critical(None, "Import Error", f"Could not import application core module.\nError: {e}")
    else:
        print(f"ERROR: Could not import application core module.\nError: {e}")
    sys.exit(1)

GITHUB_REPOSITORY_URL = "https://github.com/Midawek/ARC9-Sticker-Pack-Maker"
GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/Midawek/ARC9-Sticker-Pack-Maker/releases/latest"

def release_version_numbers(value):
    return tuple(int(part) for part in re.findall(r"\d+", value or ""))

def is_newer_release(latest_tag, current_version):
    latest_numbers = release_version_numbers(latest_tag)
    current_numbers = release_version_numbers(current_version)
    if latest_numbers and current_numbers:
        return latest_numbers > current_numbers
    return (latest_tag or "").strip().lower() != (current_version or "").strip().lower()

class UpdateCheckWorker(QObject):
    update_available = Signal(str, str, str)
    up_to_date = Signal(str)
    error = Signal(str)
    close = Signal()

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            request = urllib.request.Request(
                GITHUB_LATEST_RELEASE_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "ARC9-Sticker-Pack-Maker-Plus-Plus",
                },
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                release_data = json.loads(response.read().decode("utf-8"))

            latest_tag = release_data.get("tag_name") or release_data.get("name") or ""
            latest_name = release_data.get("name") or latest_tag
            release_url = release_data.get("html_url") or f"{GITHUB_REPOSITORY_URL}/releases"

            if not latest_tag:
                raise ValueError("Latest release did not include a tag name.")

            if is_newer_release(latest_tag, self.current_version):
                self.update_available.emit(latest_name, latest_tag, release_url)
            else:
                self.up_to_date.emit(latest_tag)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            self.error.emit(str(e))
        finally:
            self.close.emit()

# --- Worker for background processing ---
class Worker(QObject):
    progress = Signal(int, str, str)
    finished = Signal(str)
    warning = Signal(str)
    error = Signal(str)
    close = Signal()

    def __init__(self, output_dir, pack_name, processed_info):
        super().__init__()
        self.output_dir = output_dir
        self.pack_name = pack_name
        self.processed_info = processed_info
        self.is_running = True

    def run(self):
        try:
            core.create_addon_structure(self.output_dir, self.pack_name)

            addon_root = os.path.join(self.output_dir, f"arc9_{self.pack_name}_stickers")
            sticker_dir = os.path.join(addon_root, "materials", "stickers", self.pack_name)
            os.makedirs(sticker_dir, exist_ok=True)

            successful_images = []
            total = len(self.processed_info)
            for i, info in enumerate(self.processed_info):
                if not self.is_running:
                    break
                self.progress.emit(i, f"Processing '{info['original_name']}'...", info['path'])
                if core.process_image_to_vtf(self.output_dir, info, self.pack_name, info["compact_name"], sticker_dir):
                    successful_images.append(info)
            
            if self.is_running:
                if successful_images:
                    self.progress.emit(total, "Generating Lua script...", "")
                    packaged_images = core.package_sticker_sounds(self.output_dir, self.pack_name, successful_images)
                    core.create_lua_script(self.output_dir, self.pack_name, packaged_images)
                    self.finished.emit(self.pack_name)
                else:
                    self.warning.emit("No images were successfully converted.")
        except Exception as e:
            import traceback
            self.error.emit(f"An unexpected error occurred:\n{e}\n\n{traceback.format_exc()}")
        finally:
            self.close.emit()

# --- Animated Button ---
class AnimatedButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._color = QColor("#4c005f")
        self.animation = QPropertyAnimation(self, b"color")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

    def enterEvent(self, event):
        self.animation.setEndValue(QColor("#bf00be"))
        self.animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animation.setEndValue(QColor("#4c005f"))
        self.animation.start()
        super().leaveEvent(event)

    @Property(QColor)
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._color = value
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color.name()};
                color: #e0e0e0;
                border: none;
                padding: 8px 16px;
                font-family: 'Venryn Sans';
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton:pressed {{
                background-color: #3a004a;
            }}
        """)

class IconButton(QPushButton):
    def __init__(self, icon_path, tooltip, parent=None):
        super().__init__(parent)
        self.setObjectName("iconButton")
        self.setFixedSize(40, 40)
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(22, 22))

# --- Drag-and-Drop support for folder selection ---
class DropLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].isLocalFile():
                if os.path.isdir(urls[0].toLocalFile()):
                    event.acceptProposedAction()

    def dropEvent(self, event):
        path = event.mimeData().urls()[0].toLocalFile()
        self.setText(path)

class SoundDropLineEdit(QLineEdit):
    SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".ogg"}

    def __init__(self, multiple=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.multiple = multiple
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if self.sound_paths_from_event(event):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if self.sound_paths_from_event(event):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = self.sound_paths_from_event(event)
        if not paths:
            return
        if self.multiple:
            existing_paths = [path.strip() for path in self.text().split(",") if path.strip()]
            self.setText(", ".join(existing_paths + paths))
        else:
            self.setText(paths[0])
        event.acceptProposedAction()

    def sound_paths_from_event(self, event):
        if not event.mimeData().hasUrls():
            return []
        paths = []
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if os.path.isfile(path) and os.path.splitext(path)[1].lower() in self.SUPPORTED_EXTENSIONS:
                paths.append(path)
        if not self.multiple and len(paths) != 1:
            return []
        return paths

class ThumbnailCell(QWidget):
    def __init__(self, image_info, parent=None):
        super().__init__(parent)
        self.setObjectName("thumbnailCell")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("selected", False)
        self._highlight = QColor("#202020")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        self.preview = QLabel()
        self.preview.setObjectName("thumbnailPreview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedSize(128, 112)
        layout.addWidget(self.preview, alignment=Qt.AlignCenter)

        self.name_label = QLabel(image_info["original_name"])
        self.name_label.setObjectName("thumbnailName")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setToolTip(image_info["original_name"])
        layout.addWidget(self.name_label)

        self.movie = None
        if image_info["path"].lower().endswith(".gif"):
            self.movie = QMovie(image_info["path"], parent=self)
            self.movie.frameChanged.connect(self.update_movie_frame)
            self.movie.start()
        else:
            pixmap = QPixmap(image_info["path"])
            if not pixmap.isNull():
                self.preview.setPixmap(pixmap.scaled(
                    self.preview.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                ))

    def update_movie_frame(self, frame_number):
        pixmap = self.movie.currentPixmap()
        if not pixmap.isNull():
            self.preview.setPixmap(pixmap.scaled(
                self.preview.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ))

    def set_selected(self, selected, animated=True):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        target = QColor("#33223a") if selected else QColor("#202020")
        if not animated:
            self.highlight = target
            return
        self.highlight_animation = QPropertyAnimation(self, b"highlight")
        self.highlight_animation.setDuration(180)
        self.highlight_animation.setStartValue(self._highlight)
        self.highlight_animation.setEndValue(target)
        self.highlight_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.highlight_animation.start()

    @Property(QColor)
    def highlight(self):
        return self._highlight

    @highlight.setter
    def highlight(self, value):
        self._highlight = value
        border = "#bf00be" if self.property("selected") else "#343434"
        self.setStyleSheet(
            f"background-color: {value.name()}; border: 1px solid {border}; border-radius: 6px;"
        )

    def set_gif_animation_enabled(self, enabled):
        if not self.movie:
            return
        if enabled:
            self.movie.start()
        else:
            self.movie.stop()
            self.movie.jumpToFrame(0)
            self.update_movie_frame(0)

# --- Main Application Window ---
class StickerCreatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARC9 Sticker Pack Maker++")
        self.setFixedSize(1200, 850)
        # Ensure main window doesn't clip child widgets
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        # Remove margins from central widget to allow background to fill completely
        self.setContentsMargins(0, 0, 0, 0)
        logo_path = self.get_asset_path('logo.png')
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        # --- Load Custom Font ---
        font_id = QFontDatabase.addApplicationFont(self.get_asset_path('venryn-sans.regular.otf'))
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            self.setFont(QFont(font_family))
        else:
            print("Warning: Could not load custom font.")

        self.processing_data = {}
        self.worker_thread = None
        self.worker = None
        self._subfolder_default_text = "" # Initialize here
        self.remember_paths_enabled = True
        self.carry_subfolder_enabled = True
        self.autoplay_gifs_enabled = True
        self.thumbnail_size_name = "Medium"
        self.reduced_animations_enabled = False
        self.output_tree_enabled = True
        self.check_updates_on_startup_enabled = True
        self.update_check_thread = None
        self.update_check_worker = None
        self._startup_update_check_started = False
        self._startup_animation_played = False

        self.gif_movie = QMovie(self)
        self.gif_movie.frameChanged.connect(self.update_gif_frame)

        self.settings = QSettings("Midawek", "ARC9 Sticker Pack Maker++")

        self.setup_ui()
        self.apply_stylesheet()

        # --- Seamless Scrolling Background ---
        self.bg_label = QLabel(self)
        background_path = self.get_asset_path('background.png')
        bg_pixmap = QPixmap()
        if os.path.exists(background_path):
            bg_pixmap = QPixmap(background_path)
            if bg_pixmap.isNull():
                print("Warning: 'background.png' exists but could not be loaded.")
        else:
            print("Warning: 'background.png' not found in assets folder.")
        
        if not bg_pixmap.isNull() and bg_pixmap.width() > 0 and bg_pixmap.height() > 0:
            # Scale pixmap to fill window height/width with zoom (1.3x for zoomed in effect)
            zoom_factor = 1.3
            zoomed_size = QSize(int(self.width() * zoom_factor), int(self.height() * zoom_factor))
            scaled_pixmap = bg_pixmap.scaled(zoomed_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

            # Create a double-wide pixmap for seamless tiling
            tiled_pixmap = QPixmap(scaled_pixmap.width() * 2, scaled_pixmap.height())
            tiled_pixmap.fill(Qt.transparent) # Ensure transparency is kept
            painter = QPainter(tiled_pixmap)
            painter.drawPixmap(0, 0, scaled_pixmap)
            painter.drawPixmap(scaled_pixmap.width(), 0, scaled_pixmap)
            painter.end()

            self.bg_label.setPixmap(tiled_pixmap)
            # Resize label to match tiled pixmap width but window height for proper coverage
            # Position and size to cover entire window client area
            self.bg_label.resize(tiled_pixmap.width(), self.height())
            self.bg_label.move(0, 0)
            self.bg_label.setStyleSheet("background-color: #1d1d1d; margin: 0px; padding: 0px; border: none;")
            # Ensure label can display content outside window bounds and doesn't block mouse events
            self.bg_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.bg_label.lower()

            # Animation - scroll by one image width, then loop back seamlessly
            self.scroll_anim = QPropertyAnimation(self.bg_label, b"pos")
            self.scroll_anim.setDuration(50000) # 50 seconds for a slow scroll
            self.scroll_anim.setStartValue(QPoint(0, 0))
            self.scroll_anim.setEndValue(QPoint(-scaled_pixmap.width(), 0))
            self.scroll_anim.setLoopCount(-1) # Loop forever
            self.scroll_anim.setEasingCurve(QEasingCurve.Linear) # Constant speed
            # Show background by default and start animation
            self.bg_label.show()
            self.centralWidget().setAutoFillBackground(False)
            # Start animation immediately (will be toggled by settings if needed)
            self.scroll_anim.start()
        else:
            self.bg_label.hide()
            self.scroll_anim = None
            # Set dark background if no background image
            self.centralWidget().setAutoFillBackground(True)
            palette = self.centralWidget().palette()
            palette.setColor(self.centralWidget().backgroundRole(), QColor("#1d1d1d"))
            self.centralWidget().setPalette(palette)

        self.load_settings()

    def get_asset_path(self, asset_name):
        """Constructs the full path to an asset, accounting for bundled vs. source execution."""
        return os.path.join(BASE_PATH, 'assets', asset_name)


    def load_settings(self):
        self.seed_default_enabled_settings()
        background_enabled = self.settings.value("background_enabled", True, type=bool)

        self.bg_checkbox.setChecked(background_enabled)
        # Only toggle if background exists, otherwise it's already set up correctly
        if hasattr(self, 'bg_label') and self.bg_label.pixmap() and not self.bg_label.pixmap().isNull():
            self.toggle_background(background_enabled)

        # --- QOL: Load last used paths ---
        image_folder = self.settings.value("image_folder_path", "", type=str)
        output_folder = self.settings.value("output_folder_path", str(OUTPUT_BASE_PATH), type=str)
        if image_folder and os.path.isdir(image_folder):
            self.img_folder_path.setText(image_folder)
        if output_folder and os.path.isdir(output_folder):
            self.out_folder_path.setText(output_folder)

        self._subfolder_default_text = self.settings.value("subfolder_default_text", "", type=str)
        self.remember_paths_enabled = self.settings.value("remember_paths_enabled", True, type=bool)
        self.carry_subfolder_enabled = self.settings.value("carry_subfolder_enabled", True, type=bool)
        self.autoplay_gifs_enabled = self.settings.value("autoplay_gifs_enabled", True, type=bool)
        self.thumbnail_size_name = self.settings.value("thumbnail_size_name", "Medium", type=str)
        self.reduced_animations_enabled = self.settings.value("reduced_animations_enabled", False, type=bool)
        self.output_tree_enabled = self.settings.value("output_tree_enabled", True, type=bool)
        self.check_updates_on_startup_enabled = self.settings.value("check_updates_on_startup_enabled", True, type=bool)

        self.remember_paths_checkbox.setChecked(self.remember_paths_enabled)
        self.carry_subfolder_checkbox.setChecked(self.carry_subfolder_enabled)
        self.autoplay_gifs_checkbox.setChecked(self.autoplay_gifs_enabled)
        self.output_tree_checkbox.setChecked(self.output_tree_enabled)
        self.check_updates_checkbox.setChecked(self.check_updates_on_startup_enabled)
        self.thumbnail_size_combo.setCurrentText(self.thumbnail_size_name)
        self.reduced_animations_checkbox.setChecked(self.reduced_animations_enabled)
        self.apply_thumbnail_size(self.thumbnail_size_name)
        self.apply_output_tree_visibility()

    def seed_default_enabled_settings(self):
        defaults_key = "defaults_seeded_2026_05_31"
        if self.settings.value(defaults_key, False, type=bool):
            return
        self.settings.setValue("autoplay_gifs_enabled", True)
        self.settings.setValue("output_tree_enabled", True)
        self.settings.setValue("check_updates_on_startup_enabled", True)
        self.settings.setValue(defaults_key, True)

    def save_settings(self):
        self.settings.setValue("background_enabled", self.bg_checkbox.isChecked())
        # --- QOL: Save last used paths ---
        if self.remember_paths_checkbox.isChecked():
            self.settings.setValue("image_folder_path", self.img_folder_path.text())
            self.settings.setValue("output_folder_path", self.out_folder_path.text())
        else:
            self.settings.remove("image_folder_path")
            self.settings.remove("output_folder_path")
        self.settings.setValue("subfolder_default_text", self._subfolder_default_text)
        self.settings.setValue("remember_paths_enabled", self.remember_paths_checkbox.isChecked())
        self.settings.setValue("carry_subfolder_enabled", self.carry_subfolder_checkbox.isChecked())
        self.settings.setValue("autoplay_gifs_enabled", self.autoplay_gifs_checkbox.isChecked())
        self.settings.setValue("thumbnail_size_name", self.thumbnail_size_combo.currentText())
        self.settings.setValue("reduced_animations_enabled", self.reduced_animations_checkbox.isChecked())
        self.settings.setValue("output_tree_enabled", self.output_tree_checkbox.isChecked())
        self.settings.setValue("check_updates_on_startup_enabled", self.check_updates_checkbox.isChecked())

    def toggle_background(self, state):
        if hasattr(self, 'scroll_anim') and self.scroll_anim:
            if state:
                self.bg_label.show()
                self.scroll_anim.start()
                self.centralWidget().setAutoFillBackground(False)
            else:
                self.bg_label.hide()
                self.scroll_anim.stop()
                self.centralWidget().setAutoFillBackground(True)
                palette = self.centralWidget().palette()
                palette.setColor(self.centralWidget().backgroundRole(), QColor("#1d1d1d"))
                self.centralWidget().setPalette(palette)
        self.save_settings()

    def setup_ui(self):
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self.stacked_widget)

        self.setup_widget = self.create_setup_widget()
        self.processing_widget = self.create_processing_widget()
        self.settings_widget = self.create_settings_widget()

        # --- Animation: Add opacity effects for fading ---
        self.setup_widget.setGraphicsEffect(QGraphicsOpacityEffect(self))
        self.processing_widget.setGraphicsEffect(QGraphicsOpacityEffect(self))
        self.settings_widget.setGraphicsEffect(QGraphicsOpacityEffect(self))
        self.setup_widget.graphicsEffect().setOpacity(1.0)
        self.processing_widget.graphicsEffect().setOpacity(1.0)
        self.settings_widget.graphicsEffect().setOpacity(1.0)

        self.stacked_widget.addWidget(self.setup_widget)
        self.stacked_widget.addWidget(self.processing_widget)
        self.stacked_widget.addWidget(self.settings_widget)

    def create_setup_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(20, 20, 20, 20)

        # Top layout for settings button
        top_layout = QHBoxLayout()
        top_layout.addStretch()
        self.settings_button = IconButton(
            self.get_asset_path('settings.svg'),
            "Open settings",
            self,
        )
        self.settings_button.clicked.connect(self.show_settings_widget)
        top_layout.addWidget(self.settings_button)
        layout.addLayout(top_layout)

        # Banner
        self.banner_label = QLabel()
        pixmap = QPixmap(self.get_asset_path('banner.png'))
        if not pixmap.isNull():
            scaled_banner = pixmap.scaled(850, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.banner_label.setPixmap(scaled_banner)
            self.banner_label.setFixedHeight(scaled_banner.height())
        self.banner_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.banner_label)
        layout.addSpacing(28)

        # Form
        self.setup_form_frame = QFrame()
        self.setup_form_frame.setObjectName("formFrame")
        form_layout = QVBoxLayout(self.setup_form_frame)

        # Image Folder
        img_folder_layout = QHBoxLayout()
        img_folder_label = QLabel("Source Folder:")
        img_folder_label.setMinimumWidth(120)
        self.img_folder_path = DropLineEdit()
        self.img_folder_path.setPlaceholderText("Select or drop the folder containing your sticker images...")
        self.img_folder_path.setReadOnly(True)
        self.img_folder_path.setToolTip("Choose the folder containing the images and GIFs to turn into stickers.")
        img_folder_btn = QPushButton("Browse...")
        img_folder_btn.clicked.connect(self.browse_image_folder)
        img_folder_btn.setToolTip("Browse for the source folder")
        img_folder_layout.addWidget(img_folder_label)
        img_folder_layout.addWidget(self.img_folder_path)
        img_folder_layout.addWidget(img_folder_btn)
        form_layout.addLayout(img_folder_layout)
        form_layout.addSpacing(10)

        # Output Folder
        out_folder_layout = QHBoxLayout()
        out_folder_label = QLabel("Output Folder:")
        out_folder_label.setMinimumWidth(120)
        self.out_folder_path = DropLineEdit(str(OUTPUT_BASE_PATH))
        self.out_folder_path.setReadOnly(True)
        self.out_folder_path.setToolTip("Choose where the generated addon folder will be saved.")
        out_folder_btn = QPushButton("Browse...")
        out_folder_btn.clicked.connect(self.browse_output_folder)
        out_folder_btn.setToolTip("Choose a different output folder")
        out_folder_layout.addWidget(out_folder_label)
        out_folder_layout.addWidget(self.out_folder_path)
        out_folder_layout.addWidget(out_folder_btn)
        form_layout.addLayout(out_folder_layout)
        form_layout.addSpacing(10)

        # Pack Name
        pack_name_layout = QHBoxLayout()
        pack_name_label = QLabel("Pack Name:")
        pack_name_label.setMinimumWidth(120)
        self.pack_name = QLineEdit()
        self.pack_name.setPlaceholderText("Name this sticker pack...")
        self.pack_name.setToolTip("This name is used for the generated addon and sticker material paths.")
        self.pack_name.returnPressed.connect(self.start_processing)  # Enter key support
        pack_name_layout.addWidget(pack_name_label)
        pack_name_layout.addWidget(self.pack_name)
        form_layout.addLayout(pack_name_layout)
        
        layout.addWidget(self.setup_form_frame)
        layout.addStretch(1)

        # Start Button
        start_button = AnimatedButton("Continue")
        start_button.clicked.connect(self.start_processing)
        start_button.setToolTip("Open the sticker editor")
        layout.addWidget(start_button, alignment=Qt.AlignCenter)
        
        layout.addSpacing(20)
        
        # Links Section - Create a container widget for proper centering
        links_container = QWidget()
        links_layout = QHBoxLayout(links_container)
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_layout.addStretch()
        
        # GitHub Repository Link
        github_repo_label = QLabel("GitHub")
        github_repo_label.setStyleSheet("""
            QLabel {
                color: #e6a4f5;
                text-decoration: underline;
                padding: 5px;
            }
            QLabel:hover {
                color: #bf00be;
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
        """)
        github_repo_label.setCursor(Qt.PointingHandCursor)
        github_repo_label.mousePressEvent = lambda e: QDesktopServices.openUrl(QUrl("https://github.com/Midawek/ARC9-Sticker-Pack-Maker"))
        github_repo_label.setToolTip("Open GitHub repository")
        links_layout.addWidget(github_repo_label)
        
        # Separator
        separator1 = QLabel("•")
        separator1.setStyleSheet("color: #666666; padding: 5px;")
        links_layout.addWidget(separator1)
        
        # Issues Link
        issues_label = QLabel("Issues")
        issues_label.setStyleSheet("""
            QLabel {
                color: #e6a4f5;
                text-decoration: underline;
                padding: 5px;
            }
            QLabel:hover {
                color: #bf00be;
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
        """)
        issues_label.setCursor(Qt.PointingHandCursor)
        issues_label.mousePressEvent = lambda e: QDesktopServices.openUrl(QUrl("https://github.com/Midawek/ARC9-Sticker-Pack-Maker/issues"))
        issues_label.setToolTip("Report issues or provide feedback")
        links_layout.addWidget(issues_label)
        
        # Separator
        separator2 = QLabel("•")
        separator2.setStyleSheet("color: #666666; padding: 5px;")
        links_layout.addWidget(separator2)
        
        # Midawek Website Link
        website_label = QLabel("midawek.xyz")
        website_label.setStyleSheet("""
            QLabel {
                color: #e6a4f5;
                text-decoration: underline;
                padding: 5px;
            }
            QLabel:hover {
                color: #bf00be;
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
        """)
        website_label.setCursor(Qt.PointingHandCursor)
        website_label.mousePressEvent = lambda e: QDesktopServices.openUrl(QUrl("https://midawek.xyz"))
        website_label.setToolTip("Visit midawek.xyz")
        links_layout.addWidget(website_label)
        
        links_layout.addStretch()
        layout.addWidget(links_container, alignment=Qt.AlignCenter)

        return widget

    def create_settings_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QHBoxLayout()
        back_button = QPushButton("< Back")
        back_button.clicked.connect(self.show_setup_widget)
        header_layout.addWidget(back_button)
        header_layout.addStretch()
        title_label = QLabel("Settings")
        title_label.setObjectName("header")
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        spacer = QWidget()
        spacer.setFixedWidth(back_button.sizeHint().width())
        header_layout.addWidget(spacer)
        layout.addLayout(header_layout)
        layout.addSpacing(20)

        appearance_frame = QFrame()
        appearance_frame.setObjectName("settingsSection")
        appearance_layout = QVBoxLayout(appearance_frame)

        appearance_title = QLabel("Appearance")
        appearance_title.setObjectName("sectionTitle")
        appearance_layout.addWidget(appearance_title)

        background_row = QFrame()
        background_row.setObjectName("settingsRow")
        background_layout = QHBoxLayout(background_row)
        background_layout.setContentsMargins(0, 0, 0, 0)
        background_text_layout = QVBoxLayout()
        background_text_layout.setSpacing(2)
        background_title = QLabel("Animated background")
        background_title.setObjectName("settingsLabel")
        background_caption = QLabel("Scroll the background texture while the app is open.")
        background_caption.setObjectName("settingsCaption")
        background_text_layout.addWidget(background_title)
        background_text_layout.addWidget(background_caption)
        background_layout.addLayout(background_text_layout)
        background_layout.addStretch()
        self.bg_checkbox = QCheckBox()
        self.bg_checkbox.setObjectName("settingsToggle")
        self.bg_checkbox.setChecked(True)
        self.bg_checkbox.stateChanged.connect(self.toggle_background)
        background_layout.addWidget(self.bg_checkbox)
        appearance_layout.addWidget(background_row)
        self.reduced_animations_checkbox = self.create_settings_toggle_row(
            appearance_layout,
            "Reduced animations",
            "Use gentler transitions and keep decorative motion to a minimum.",
            self.on_reduced_animations_changed,
        )

        layout.addWidget(appearance_frame)
        layout.addSpacing(14)

        workflow_frame = QFrame()
        workflow_frame.setObjectName("settingsSection")
        workflow_layout = QVBoxLayout(workflow_frame)

        workflow_title = QLabel("Workflow")
        workflow_title.setObjectName("sectionTitle")
        workflow_layout.addWidget(workflow_title)

        self.remember_paths_checkbox = self.create_settings_toggle_row(
            workflow_layout,
            "Remember folders",
            "Restore the last source and output folders on launch.",
            self.on_remember_paths_changed,
        )
        self.carry_subfolder_checkbox = self.create_settings_toggle_row(
            workflow_layout,
            "Carry subfolder forward",
            "Use the last entered subfolder as the default for new stickers.",
            self.on_carry_subfolder_changed,
        )
        self.autoplay_gifs_checkbox = self.create_settings_toggle_row(
            workflow_layout,
            "Autoplay GIF previews",
            "Animate GIFs in the editor preview instead of showing a still frame.",
            self.on_autoplay_gifs_changed,
        )
        self.output_tree_checkbox = self.create_settings_toggle_row(
            workflow_layout,
            "Show output tree",
            "Preview the generated addon folders below the sticker library.",
            self.on_output_tree_changed,
        )
        self.check_updates_checkbox = self.create_settings_toggle_row(
            workflow_layout,
            "Check for updates",
            f"Look for new GitHub releases on startup. Current version: {APP_VERSION}.",
            self.on_check_updates_changed,
        )

        update_row = QFrame()
        update_row.setObjectName("settingsRow")
        update_layout = QHBoxLayout(update_row)
        update_layout.setContentsMargins(0, 0, 0, 0)
        update_text_layout = QVBoxLayout()
        update_text_layout.setSpacing(2)
        update_title = QLabel("GitHub releases")
        update_title.setObjectName("settingsLabel")
        self.update_status_label = QLabel("Ready to check for updates.")
        self.update_status_label.setObjectName("settingsCaption")
        update_text_layout.addWidget(update_title)
        update_text_layout.addWidget(self.update_status_label)
        update_layout.addLayout(update_text_layout)
        update_layout.addStretch()
        self.check_now_button = QPushButton("Check Now")
        self.check_now_button.clicked.connect(lambda: self.check_for_updates(manual=True))
        update_layout.addWidget(self.check_now_button)
        workflow_layout.addWidget(update_row)

        thumbnail_row = QFrame()
        thumbnail_row.setObjectName("settingsRow")
        thumbnail_layout = QHBoxLayout(thumbnail_row)
        thumbnail_layout.setContentsMargins(0, 0, 0, 0)
        thumbnail_text_layout = QVBoxLayout()
        thumbnail_text_layout.setSpacing(2)
        thumbnail_title = QLabel("Thumbnail size")
        thumbnail_title.setObjectName("settingsLabel")
        thumbnail_caption = QLabel("Choose how dense the sticker library should be.")
        thumbnail_caption.setObjectName("settingsCaption")
        thumbnail_text_layout.addWidget(thumbnail_title)
        thumbnail_text_layout.addWidget(thumbnail_caption)
        thumbnail_layout.addLayout(thumbnail_text_layout)
        thumbnail_layout.addStretch()
        self.thumbnail_size_combo = QComboBox()
        self.thumbnail_size_combo.addItems(["Small", "Medium", "Large"])
        self.thumbnail_size_combo.currentTextChanged.connect(self.on_thumbnail_size_changed)
        thumbnail_layout.addWidget(self.thumbnail_size_combo)
        workflow_layout.addWidget(thumbnail_row)

        layout.addWidget(workflow_frame)
        layout.addStretch()

        return widget

    def create_settings_toggle_row(self, parent_layout, title, caption, handler):
        row = QFrame()
        row.setObjectName("settingsRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("settingsLabel")
        caption_label = QLabel(caption)
        caption_label.setObjectName("settingsCaption")
        text_layout.addWidget(title_label)
        text_layout.addWidget(caption_label)
        row_layout.addLayout(text_layout)
        row_layout.addStretch()
        checkbox = QCheckBox()
        checkbox.setObjectName("settingsToggle")
        checkbox.stateChanged.connect(handler)
        row_layout.addWidget(checkbox)
        parent_layout.addWidget(row)
        return checkbox

    def on_remember_paths_changed(self, state):
        self.remember_paths_enabled = bool(state)
        self.save_settings()

    def on_carry_subfolder_changed(self, state):
        self.carry_subfolder_enabled = bool(state)
        self.save_settings()

    def on_autoplay_gifs_changed(self, state):
        self.autoplay_gifs_enabled = bool(state)
        for cell in getattr(self, "thumbnail_cells", []):
            cell.set_gif_animation_enabled(self.autoplay_gifs_enabled)
        if self.processing_data:
            self.show_current_image()
        self.save_settings()

    def on_output_tree_changed(self, state):
        self.output_tree_enabled = bool(state)
        self.apply_output_tree_visibility()
        self.save_settings()

    def on_check_updates_changed(self, state):
        self.check_updates_on_startup_enabled = bool(state)
        self.save_settings()

    def on_thumbnail_size_changed(self, size_name):
        self.thumbnail_size_name = size_name
        self.apply_thumbnail_size(size_name)
        if self.processing_data:
            self.populate_sticker_gallery(self.processing_data["images"])
            self.show_current_image()
        self.save_settings()

    def on_reduced_animations_changed(self, state):
        self.reduced_animations_enabled = bool(state)
        if hasattr(self, "scroll_anim") and self.scroll_anim:
            if self.reduced_animations_enabled:
                self.scroll_anim.stop()
                self.bg_label.move(0, 0)
            elif self.bg_checkbox.isChecked():
                self.scroll_anim.start()
        self.save_settings()

    def apply_thumbnail_size(self, size_name):
        presets = {
            "Small": (96, 84, 120, 142),
            "Medium": (128, 112, 145, 165),
            "Large": (160, 140, 182, 198),
        }
        preview_w, preview_h, grid_w, grid_h = presets.get(size_name, presets["Medium"])
        self.sticker_gallery.setIconSize(QSize(preview_w, preview_h))
        self.sticker_gallery.setGridSize(QSize(grid_w, grid_h))

    def apply_output_tree_visibility(self):
        if not hasattr(self, "output_tree_frame"):
            return
        processing_active = (
            hasattr(self, "progress_frame")
            and self.progress_frame.isVisible()
        )
        self.output_tree_frame.setVisible(self.output_tree_enabled and not processing_active)

    def switch_view(self, new_widget):
        """ Animates the transition between stacked widget pages. """
        current_widget = self.stacked_widget.currentWidget()
        if current_widget is new_widget:
            return
        if self.reduced_animations_enabled:
            current_widget.graphicsEffect().setOpacity(1.0)
            new_widget.graphicsEffect().setOpacity(1.0)
            self.stacked_widget.setCurrentWidget(new_widget)
            return

        # Fade out current widget
        self.fade_out_animation = QPropertyAnimation(current_widget.graphicsEffect(), b"opacity")
        self.fade_out_animation.setDuration(170)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.InCubic)
        
        # After fade-out, switch widget and fade in
        def on_finished():
            current_widget.graphicsEffect().setOpacity(1.0) # Reset for next time
            self.stacked_widget.setCurrentWidget(new_widget)
            new_widget.graphicsEffect().setOpacity(0.0) # Start transparent

            self.fade_in_animation = QPropertyAnimation(new_widget.graphicsEffect(), b"opacity")
            self.fade_in_animation.setDuration(220)
            self.fade_in_animation.setStartValue(0.0)
            self.fade_in_animation.setEndValue(1.0)
            self.fade_in_animation.setEasingCurve(QEasingCurve.OutCubic)

            start_pos = new_widget.pos() + QPoint(0, 10)
            self.slide_in_animation = QPropertyAnimation(new_widget, b"pos")
            self.slide_in_animation.setDuration(220)
            self.slide_in_animation.setStartValue(start_pos)
            self.slide_in_animation.setEndValue(new_widget.pos())
            self.slide_in_animation.setEasingCurve(QEasingCurve.OutCubic)

            self.page_enter_animation = QParallelAnimationGroup(self)
            self.page_enter_animation.addAnimation(self.fade_in_animation)
            self.page_enter_animation.addAnimation(self.slide_in_animation)
            self.page_enter_animation.start()

        self.fade_out_animation.finished.connect(on_finished)
        self.fade_out_animation.start()

    def show_settings_widget(self):
        self.switch_view(self.settings_widget)

    def show_setup_widget(self):
        self.switch_view(self.setup_widget)

    def animate_startup(self):
        if self.reduced_animations_enabled:
            return
        self.setup_widget.graphicsEffect().setOpacity(0.0)
        self.startup_page_fade = QPropertyAnimation(self.setup_widget.graphicsEffect(), b"opacity")
        self.startup_page_fade.setDuration(260)
        self.startup_page_fade.setStartValue(0.0)
        self.startup_page_fade.setEndValue(1.0)
        self.startup_page_fade.setEasingCurve(QEasingCurve.OutCubic)
        self.startup_page_fade.start()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._startup_animation_played:
            self._startup_animation_played = True
            self.animate_startup()
        if self.check_updates_on_startup_enabled and not self._startup_update_check_started:
            self._startup_update_check_started = True
            self.check_for_updates(manual=False)

    def open_github(self, event):
        QDesktopServices.openUrl(QUrl(GITHUB_REPOSITORY_URL))

    def check_for_updates(self, manual=False):
        if self.update_check_thread is not None:
            if manual:
                self.update_status_label.setText("Update check already running...")
            return

        self.update_check_manual = manual
        if hasattr(self, "update_status_label"):
            self.update_status_label.setText("Checking GitHub releases...")
        if hasattr(self, "check_now_button"):
            self.check_now_button.setEnabled(False)

        self.update_check_worker = UpdateCheckWorker(APP_VERSION)
        self.update_check_thread = QThread()
        self.update_check_worker.moveToThread(self.update_check_thread)
        self.update_check_thread.started.connect(self.update_check_worker.run)
        self.update_check_worker.update_available.connect(self.on_update_available)
        self.update_check_worker.up_to_date.connect(self.on_update_up_to_date)
        self.update_check_worker.error.connect(self.on_update_check_error)
        self.update_check_worker.close.connect(self.on_update_check_finished)
        self.update_check_thread.start()

    def on_update_available(self, latest_name, latest_tag, release_url):
        if hasattr(self, "update_status_label"):
            self.update_status_label.setText(f"New release available: {latest_tag}")

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Update Available")
        msg_box.setText(f"A new version is available: {latest_name}")
        msg_box.setInformativeText(f"Current version: {APP_VERSION}")
        open_button = msg_box.addButton("Open Release", QMessageBox.ActionRole)
        msg_box.addButton("Later", QMessageBox.RejectRole)
        msg_box.exec()
        if msg_box.clickedButton() == open_button:
            QDesktopServices.openUrl(QUrl(release_url))

    def on_update_up_to_date(self, latest_tag):
        if hasattr(self, "update_status_label"):
            self.update_status_label.setText(f"Up to date: {latest_tag}")
        if getattr(self, "update_check_manual", False):
            QMessageBox.information(self, "No Update Found", f"You are on the latest release ({latest_tag}).")

    def on_update_check_error(self, message):
        if hasattr(self, "update_status_label"):
            self.update_status_label.setText("Could not check GitHub releases.")
        if getattr(self, "update_check_manual", False):
            QMessageBox.warning(self, "Update Check Failed", f"Could not check for updates:\n\n{message}")

    def on_update_check_finished(self):
        if self.update_check_thread:
            self.update_check_thread.quit()
            self.update_check_thread.wait()
        self.update_check_thread = None
        self.update_check_worker = None
        if hasattr(self, "check_now_button"):
            self.check_now_button.setEnabled(True)

    def create_processing_widget(self):
        widget = QWidget()
        self.processing_layout = QVBoxLayout(widget)
        self.processing_layout.setContentsMargins(20, 20, 20, 20)

        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setChildrenCollapsible(False)
        self.processing_layout.addWidget(content_splitter)

        self.gallery_frame = QFrame()
        self.gallery_frame.setObjectName("galleryFrame")
        gallery_layout = QVBoxLayout(self.gallery_frame)
        gallery_layout.setContentsMargins(12, 12, 12, 12)

        gallery_header_layout = QHBoxLayout()
        self.gallery_label = QLabel("Sticker Library")
        self.gallery_label.setObjectName("galleryHeader")
        self.gallery_count_label = QLabel()
        self.gallery_count_label.setObjectName("galleryCount")
        gallery_header_layout.addWidget(self.gallery_label)
        gallery_header_layout.addStretch()
        gallery_header_layout.addWidget(self.gallery_count_label)
        gallery_layout.addLayout(gallery_header_layout)

        self.gallery_search = QLineEdit()
        self.gallery_search.setObjectName("gallerySearch")
        self.gallery_search.setPlaceholderText("Search stickers...")
        self.gallery_search.textChanged.connect(self.filter_sticker_gallery)
        gallery_layout.addWidget(self.gallery_search)

        self.sticker_gallery = QListWidget()
        self.sticker_gallery.setObjectName("stickerGallery")
        self.sticker_gallery.setViewMode(QListWidget.IconMode)
        self.sticker_gallery.setResizeMode(QListWidget.Adjust)
        self.sticker_gallery.setMovement(QListWidget.Static)
        self.sticker_gallery.setWrapping(True)
        self.sticker_gallery.setSpacing(10)
        self.sticker_gallery.setIconSize(QSize(120, 120))
        self.sticker_gallery.setGridSize(QSize(145, 165))
        self.sticker_gallery.setSelectionMode(QListWidget.SingleSelection)
        self.sticker_gallery.setFocusPolicy(Qt.NoFocus)
        self.sticker_gallery.currentRowChanged.connect(self.on_gallery_row_changed)

        self.output_tree_frame = QFrame()
        self.output_tree_frame.setObjectName("outputTreeFrame")
        output_tree_layout = QVBoxLayout(self.output_tree_frame)
        output_tree_layout.setContentsMargins(10, 10, 10, 10)
        output_tree_header = QLabel("Output Tree")
        output_tree_header.setObjectName("galleryHeader")
        output_tree_layout.addWidget(output_tree_header)
        self.output_tree = QTreeWidget()
        self.output_tree.setObjectName("outputTree")
        self.output_tree.setHeaderHidden(True)
        self.output_tree.setAnimated(True)
        self.output_tree.setMinimumHeight(120)
        output_tree_layout.addWidget(self.output_tree)

        self.gallery_content_splitter = QSplitter(Qt.Vertical)
        self.gallery_content_splitter.setChildrenCollapsible(False)
        self.gallery_content_splitter.addWidget(self.sticker_gallery)
        self.gallery_content_splitter.addWidget(self.output_tree_frame)
        self.gallery_content_splitter.setSizes([520, 190])
        gallery_layout.addWidget(self.gallery_content_splitter)
        content_splitter.addWidget(self.gallery_frame)

        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(12, 0, 0, 0)
        content_splitter.addWidget(editor_panel)
        content_splitter.setSizes([620, 520])

        self.header_label = QLabel("Editing Sticker 1 of N")
        self.header_label.setObjectName("header")
        self.header_label.setAlignment(Qt.AlignCenter)
        editor_layout.addWidget(self.header_label)

        self.image_preview = QLabel("Select a sticker to preview it")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumSize(420, 390)
        self.image_preview.setObjectName("imagePreview")
        editor_layout.addWidget(self.image_preview)
        self.gif_movie = QMovie(self)
        self.gif_movie.frameChanged.connect(self.update_gif_frame)

        # Details Frame
        self.details_frame = QFrame()
        self.details_frame.setObjectName("formFrame")
        details_layout = QVBoxLayout(self.details_frame)

        # Display Name
        name_layout = QHBoxLayout()
        name_label = QLabel("In-game Name:")
        name_label.setFixedWidth(105)
        self.print_name_edit = QLineEdit()
        self.print_name_edit.setToolTip("The name players will see in-game.")
        self.print_name_edit.returnPressed.connect(self.next_image)  # Enter key support
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.print_name_edit, 1)
        details_layout.addLayout(name_layout)
        details_layout.addSpacing(8)

        # Compact Name
        compact_layout = QHBoxLayout()
        compact_label = QLabel("Material Name:")
        compact_label.setFixedWidth(105)
        self.compact_name_edit = QLineEdit()
        self.compact_name_edit.setPlaceholderText("Optional; generated from the in-game name when left blank")
        self.compact_name_edit.setToolTip("Optional filename-friendly material name. Leave blank to generate it automatically.")
        self.compact_name_edit.returnPressed.connect(self.next_image)
        compact_layout.addWidget(compact_label)
        compact_layout.addWidget(self.compact_name_edit, 1)
        details_layout.addLayout(compact_layout)
        details_layout.addSpacing(8)

        # Description
        desc_layout = QHBoxLayout()
        desc_label = QLabel("Description:")
        desc_label.setFixedWidth(105)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Optional sticker description...")
        self.desc_edit.setToolTip("Optional description shown with the sticker attachment.")
        desc_layout.addWidget(desc_label)
        desc_layout.addWidget(self.desc_edit, 1)
        details_layout.addLayout(desc_layout)
        details_layout.addSpacing(8)

        # Subfolder
        subfolder_layout = QHBoxLayout()
        subfolder_label = QLabel("Subfolder:")
        subfolder_label.setFixedWidth(105)
        self.subfolder_edit = QLineEdit()
        self.subfolder_edit.setPlaceholderText("Optional, e.g. Characters/Cute")
        self.subfolder_edit.setToolTip("Optional folder path for organizing stickers in-game.")
        self.subfolder_edit.setText(self._subfolder_default_text) # Set initial text here
        subfolder_layout.addWidget(subfolder_label)
        subfolder_layout.addWidget(self.subfolder_edit, 1)
        details_layout.addLayout(subfolder_layout)
        details_layout.addSpacing(10)

        effects_title = QLabel("Sticker FX")
        effects_title.setObjectName("sectionTitle")
        effects_title.setToolTip("Optional ARC9 sound effects generated into the attachment Lua.")
        details_layout.addWidget(effects_title)

        self.install_sound_edit = self.create_sound_input_row(
            details_layout,
            "Install Sound:",
            "Optional sound file or ARC9 path",
            "Sound played when the sticker is equipped.",
        )
        self.uninstall_sound_edit = self.create_sound_input_row(
            details_layout,
            "Uninstall Sound:",
            "Optional sound file or ARC9 path",
            "Sound played when the sticker is removed.",
        )
        self.impact_sound_edit = self.create_sound_input_row(
            details_layout,
            "Impact Sound:",
            "Optional sound file or ARC9 path",
            "Impact sound included in the generated FX Enabled toggle.",
        )
        self.shoot_sounds_edit = self.create_sound_input_row(
            details_layout,
            "Shoot Sounds:",
            "Optional sound files or comma-separated ARC9 paths",
            "Shoot sounds for both outdoor and indoor fire.",
            multiple=True,
        )
        self.shoot_silenced_sounds_edit = self.create_sound_input_row(
            details_layout,
            "Silenced Sounds:",
            "Optional sound files or comma-separated ARC9 paths",
            "Silenced shoot sounds for both outdoor and indoor fire.",
            multiple=True,
        )
        self.dryfire_sounds_edit = self.create_sound_input_row(
            details_layout,
            "Dry Fire Sounds:",
            "Optional sound files or comma-separated ARC9 paths",
            "Dry-fire sounds for the FX Enabled toggle.",
            multiple=True,
        )
        self.details_scroll = QScrollArea()
        self.details_scroll.setObjectName("detailsScroll")
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setFrameShape(QFrame.NoFrame)
        self.details_scroll.setMaximumHeight(315)
        self.details_scroll.setWidget(self.details_frame)
        editor_layout.addWidget(self.details_scroll)
        self.connect_output_tree_updates()

        # Progress Frame (initially hidden)
        self.progress_frame = QFrame()
        progress_layout = QVBoxLayout(self.progress_frame)
        self.progress_label = QLabel("Initializing...")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        editor_layout.addWidget(self.progress_frame)
        self.progress_frame.setVisible(False)

        editor_layout.addStretch()

        # Button Frame
        self.button_frame = QFrame()
        button_layout = QHBoxLayout(self.button_frame)
        button_layout.setContentsMargins(0,0,0,0)
        self.back_button = QPushButton("< Back")
        self.back_button.clicked.connect(self.handle_back_action)
        self.back_button.setToolTip("Return to the previous screen or sticker")
        self.next_button = AnimatedButton("Next Sticker >")
        self.next_button.clicked.connect(self.next_image)
        self.next_button.setToolTip("Save this sticker and continue")
        button_layout.addWidget(self.back_button)
        button_layout.addStretch()
        button_layout.addWidget(self.next_button)
        editor_layout.addWidget(self.button_frame)

        return widget

    def connect_output_tree_updates(self):
        for line_edit in (
            self.print_name_edit,
            self.compact_name_edit,
            self.subfolder_edit,
            self.install_sound_edit,
            self.uninstall_sound_edit,
            self.impact_sound_edit,
            self.shoot_sounds_edit,
            self.shoot_silenced_sounds_edit,
            self.dryfire_sounds_edit,
        ):
            line_edit.textChanged.connect(self.update_output_tree)

    def create_sound_input_row(self, parent_layout, label_text, placeholder, tooltip, multiple=False):
        row_layout = QHBoxLayout()
        row_layout.setSpacing(6)
        label = QLabel(label_text)
        label.setFixedWidth(105)
        sound_edit = SoundDropLineEdit(multiple=multiple)
        sound_edit.setPlaceholderText(placeholder)
        sound_edit.setToolTip(tooltip)
        sound_edit.setMinimumWidth(120)
        browse_button = QPushButton("Add..." if multiple else "Browse...")
        browse_button.setFixedWidth(84)
        browse_button.setToolTip("Select one or more sound files" if multiple else "Select a sound file")
        if multiple:
            browse_button.clicked.connect(lambda: self.browse_multiple_sounds(sound_edit))
        else:
            browse_button.clicked.connect(lambda: self.browse_single_sound(sound_edit))
        row_layout.addWidget(label)
        row_layout.addWidget(sound_edit, 1)
        row_layout.addWidget(browse_button)
        parent_layout.addLayout(row_layout)
        parent_layout.addSpacing(6)
        return sound_edit

    def apply_stylesheet(self):
        stylesheet_content = f"""
            QMainWindow {{
                background-color: #2d2d2d;
            }}
            QWidget {{
                background-color: transparent;
                color: #e0e0e0;
                font-family: 'Venryn Sans', 'Segoe UI';
                font-size: 10pt;
            }}
            #formFrame {{
                background-color: #3c3c3c;
                border-radius: 8px;
                padding: 15px;
            }}
            QScrollArea#detailsScroll {{
                background-color: transparent;
                border: none;
            }}
            #outputTreeFrame {{
                background-color: rgba(25, 25, 25, 0.96);
                border: 1px solid #323232;
                border-radius: 8px;
            }}
            QTreeWidget#outputTree {{
                background-color: rgba(22, 22, 22, 0.98);
                border: 1px solid #323232;
                border-radius: 6px;
                padding: 4px;
                color: #d8d8d8;
            }}
            QTreeWidget#outputTree::item {{
                padding: 2px;
            }}
            QTreeWidget#outputTree::item:selected {{
                background-color: #33223a;
                color: #ffffff;
            }}
            #settingsSection {{
                background-color: rgba(37, 37, 37, 0.96);
                border: 1px solid #343434;
                border-radius: 8px;
                padding: 16px;
            }}
            QLabel#sectionTitle {{
                font-size: 12pt;
                font-weight: bold;
                color: #e0e0e0;
                padding: 0 0 10px 0;
            }}
            QLabel#settingsLabel {{
                font-weight: bold;
                color: #e0e0e0;
                padding: 0;
            }}
            QLabel#settingsCaption {{
                color: #9b9b9b;
                padding: 0;
            }}
            #galleryFrame {{
                background-color: rgba(25, 25, 25, 0.96);
                border: 1px solid #323232;
                border-radius: 8px;
            }}
            QLabel#galleryHeader {{
                font-size: 12pt;
                font-weight: bold;
                color: #e0e0e0;
                padding: 2px 4px 8px 4px;
            }}
            QLabel#galleryCount {{
                color: #969696;
                padding: 2px 4px 8px 4px;
            }}
            QLineEdit#gallerySearch {{
                background-color: #222222;
                border: 1px solid #3a3a3a;
                margin-bottom: 4px;
            }}
            QListWidget#stickerGallery {{
                background-color: rgba(24, 24, 24, 0.98);
                border: 1px solid #323232;
                border-radius: 6px;
                padding: 8px;
            }}
            QListWidget#stickerGallery::item {{
                background-color: transparent;
                border: none;
            }}
            QWidget#thumbnailCell {{
                background-color: #202020;
                border: 1px solid #343434;
                border-radius: 6px;
            }}
            QWidget#thumbnailCell[selected="true"] {{
                background-color: #29212d;
                border: 1px solid #bf00be;
            }}
            QLabel#thumbnailPreview {{
                background-color: #151515;
                border: none;
                padding: 0;
            }}
            QLabel#thumbnailName {{
                color: #d8d8d8;
                padding: 0;
            }}
            QLabel {{
                padding: 5px;
            }}
            #formFrame QLabel {{
                padding-left: 0;
                padding-right: 4px;
            }}
            QLabel#header {{
                font-size: 14pt;
                font-weight: bold;
                color: #e6a4f5;
            }}
            QLineEdit {{
                background-color: #222222;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 6px;
            }}
            QLineEdit:focus {{
                border: 1px solid #bf00be;
                background-color: #2a2a2a;
            }}
            QLineEdit::placeholder {{
                color: #666666;
            }}
            QPushButton {{
                background-color: #4a4a4a;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #5a5a5a;
            }}
            QPushButton:pressed {{
                background-color: #3a3a3a;
            }}
            QPushButton#iconButton {{
                background-color: rgba(34, 34, 34, 0.88);
                border: 1px solid #3a3a3a;
                padding: 0;
            }}
            QPushButton#iconButton:hover {{
                background-color: #363036;
                border: 1px solid #bf00be;
            }}
            QPushButton#iconButton:pressed {{
                background-color: #241d26;
            }}
            QComboBox {{
                background-color: #222222;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 6px 28px 6px 8px;
                min-width: 110px;
            }}
            QCheckBox#settingsToggle::indicator {{
                width: 42px;
                height: 22px;
                border-radius: 11px;
                background-color: #262626;
                border: 1px solid #4a4a4a;
            }}
            QCheckBox#settingsToggle::indicator:checked {{
                background-color: #bf00be;
                border: 1px solid #bf00be;
            }}
            #imagePreview {{
                background-color: #222222;
                border: 1px solid #4a4a4a;
                border-radius: 8px;
            }}
            QCheckBox {{
                spacing: 10px;
            }}
            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: #222222;
                border: 1px solid #4a4a4a;
            }}
            QCheckBox::indicator:checked {{
                background-color: #bf00be;
            }}
            QProgressBar {{
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                text-align: center;
                color: #e0e0e0;
            }}
            QProgressBar::chunk {{
                background-color: #bf00be;
                border-radius: 3px;
            }}
        """
        self.setStyleSheet(stylesheet_content)

    def update_gif_frame(self, frame_number):
        pixmap = self.gif_movie.currentPixmap()
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(self.image_preview.size() * 0.95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_preview.setPixmap(scaled_pixmap)

    def browse_image_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder", dir=str(OUTPUT_BASE_PATH))
        if folder:
            self.img_folder_path.setText(folder)

    def browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", dir=str(OUTPUT_BASE_PATH))
        if folder:
            self.out_folder_path.setText(folder)

    def sound_file_filter(self):
        return "Sound Files (*.mp3 *.wav *.ogg);;All Files (*)"

    def browse_single_sound(self, target_edit):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Sound File",
            "",
            self.sound_file_filter(),
        )
        if file_path:
            target_edit.setText(file_path)

    def browse_multiple_sounds(self, target_edit):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Sound Files",
            "",
            self.sound_file_filter(),
        )
        if not file_paths:
            return
        existing_paths = [path.strip() for path in target_edit.text().split(",") if path.strip()]
        target_edit.setText(", ".join(existing_paths + file_paths))

    def add_output_tree_path(self, root_item, path_parts):
        parent = root_item
        for part in path_parts:
            existing = None
            for index in range(parent.childCount()):
                child = parent.child(index)
                if child.text(0) == part:
                    existing = child
                    break
            if existing is None:
                existing = QTreeWidgetItem([part])
                parent.addChild(existing)
            parent = existing
        return parent

    def output_tree_states(self):
        states = []
        current_index = self.processing_data.get("current_index", -1)
        for index, image_info in enumerate(self.processing_data.get("images", [])):
            state = self.processing_data["sticker_states"][index] or self.default_state_for_image(image_info)
            if index == current_index and hasattr(self, "print_name_edit"):
                state = self.current_form_state()
            states.append(state)
        return states

    def preview_sound_filenames(self, state):
        fields = (
            "install_sound",
            "uninstall_sound",
            "impact_sound",
            "shoot_sounds",
            "shoot_silenced_sounds",
            "dryfire_sounds",
        )
        filenames = []
        used_filenames = set()
        for field in fields:
            raw_paths = (
                core.split_sound_paths(state.get(field, ""))
                if field in {"shoot_sounds", "shoot_silenced_sounds", "dryfire_sounds"}
                else [state.get(field, "").strip()]
            )
            for raw_path in raw_paths:
                if not raw_path:
                    continue
                normalized_path = os.path.normpath(raw_path.strip('"'))
                if not os.path.isfile(normalized_path):
                    continue
                filename = core.sanitize_sound_filename(normalized_path)
                stem, extension = os.path.splitext(filename)
                counter = 2
                while filename.lower() in used_filenames:
                    filename = f"{stem}_{counter}{extension}"
                    counter += 1
                used_filenames.add(filename.lower())
                filenames.append(filename)
        return filenames

    def preview_compact_names_by_index(self, states):
        compact_names = {}
        for index, state in enumerate(states):
            print_name = state.get("print_name", "")
            compact_input = state.get("compact_name_input", "")
            compact_name = (
                core.sanitize_for_filename(compact_input, strict=False)
                if compact_input
                else core.sanitize_for_filename(print_name, strict=True)
            )
            compact_names[index] = compact_name or f"sticker_{index + 1}"
        return compact_names

    def update_output_tree(self):
        if not hasattr(self, "output_tree") or not self.processing_data:
            return
        self.output_tree.clear()

        pack_name = self.processing_data.get("pack_name", "stickerpack")
        root = QTreeWidgetItem([f"arc9_{pack_name}_stickers"])
        self.output_tree.addTopLevelItem(root)

        self.add_output_tree_path(root, ["lua", "arc9", "common", "attachments_bulk", f"a9sm_{pack_name}.lua"])

        states = self.output_tree_states()
        compact_names = self.preview_compact_names_by_index(states)
        for index, state in enumerate(states):
            compact_name = compact_names.get(index, f"sticker_{index + 1}")
            self.add_output_tree_path(root, ["materials", "stickers", pack_name, f"{compact_name}.vtf"])
            self.add_output_tree_path(root, ["materials", "stickers", pack_name, f"{compact_name}.vmt"])

            sound_filenames = self.preview_sound_filenames(state)
            for filename in sound_filenames:
                self.add_output_tree_path(
                    root,
                    ["sound", "arc9", pack_name, "soundmods", compact_name, filename],
                )

        self.output_tree.expandToDepth(3)

    def start_processing(self):
        image_folder = self.img_folder_path.text()
        pack_name = self.pack_name.text().strip()
        output_dir = self.out_folder_path.text()

        # Validation with better feedback
        errors = []
        if not image_folder or not os.path.isdir(image_folder):
            errors.append("• Please select a valid image folder")
            self.img_folder_path.setStyleSheet("border: 2px solid #bf00be;")
        else:
            self.img_folder_path.setStyleSheet("")
            
        if not pack_name:
            errors.append("• Pack Name cannot be empty")
            self.pack_name.setStyleSheet("border: 2px solid #bf00be;")
        else:
            self.pack_name.setStyleSheet("")
            
        if errors:
            QMessageBox.warning(self, "Validation Error", "Please fix the following:\n\n" + "\n".join(errors))
            return

        # Scan for images with progress feedback
        try:
            images_to_process = []
            for entry in core.iter_sorted_files(image_folder):
                # Use a more reliable method to check for valid images
                pixmap = QPixmap(entry.path)
                if pixmap.isNull():
                    continue  # Skip files that Qt can't read

                images_to_process.append({
                    "path": entry.path,
                    "original_name": os.path.splitext(entry.name)[0],
                })
        except PermissionError:
            QMessageBox.critical(self, "Access Error", f"Cannot access folder:\n{image_folder}\n\nPlease check folder permissions.")
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error scanning folder:\n{str(e)}")
            return

        if not images_to_process:
            QMessageBox.information(self, "No Images Found", 
                f"No compatible images found in:\n{image_folder}\n\n"
                "Supported formats: PNG, JPG, GIF\n"
                "Please ensure the folder contains image files.")
            return
            
        self.processing_data = {
            "pack_name": core.sanitize_for_filename(pack_name),
            "output_dir": output_dir,
            "images": images_to_process,
            "sticker_states": [None] * len(images_to_process),
            "current_index": 0
        }
        
        self.populate_sticker_gallery(images_to_process)
        self.switch_view(self.processing_widget)
        self.show_current_image()
        self.update_output_tree()

    def populate_sticker_gallery(self, images):
        self.sticker_gallery.clear()
        self.thumbnail_cells = []
        self.gallery_count_label.setText(f"{len(images)} items")
        for image_info in images:
            item = QListWidgetItem()
            item.setSizeHint(self.sticker_gallery.gridSize())
            item.setToolTip(image_info["original_name"])
            self.sticker_gallery.addItem(item)
            cell = ThumbnailCell(image_info, self.sticker_gallery)
            cell.preview.setFixedSize(self.sticker_gallery.iconSize())
            cell.set_gif_animation_enabled(self.autoplay_gifs_enabled)
            self.sticker_gallery.setItemWidget(item, cell)
            self.thumbnail_cells.append(cell)

    def filter_sticker_gallery(self, text):
        query = text.strip().lower()
        for index, image_info in enumerate(self.processing_data.get("images", [])):
            item = self.sticker_gallery.item(index)
            item.setHidden(query not in image_info["original_name"].lower())

    def on_gallery_row_changed(self, row):
        for index, cell in enumerate(getattr(self, "thumbnail_cells", [])):
            cell.set_selected(index == row, animated=not self.reduced_animations_enabled)
        if not self.processing_data or row < 0:
            return
        if row >= len(self.processing_data.get("images", [])):
            return
        current_index = self.processing_data.get("current_index", 0)
        if row == current_index:
            return
        self.save_current_form()
        self.processing_data["current_index"] = row
        self.show_current_image()

    def default_state_for_image(self, image_info):
        return {
            "print_name": image_info["original_name"].replace('_', ' ').title(),
            "compact_name_input": "",
            "description": "",
            "subfolder": self._subfolder_default_text if self.carry_subfolder_enabled else "",
            "install_sound": "",
            "uninstall_sound": "",
            "impact_sound": "",
            "shoot_sounds": "",
            "shoot_silenced_sounds": "",
            "dryfire_sounds": "",
        }

    def current_form_state(self):
        return {
            "print_name": self.print_name_edit.text().strip(),
            "compact_name_input": self.compact_name_edit.text().strip(),
            "description": self.desc_edit.text(),
            "subfolder": self.subfolder_edit.text().strip(),
            "install_sound": self.install_sound_edit.text().strip(),
            "uninstall_sound": self.uninstall_sound_edit.text().strip(),
            "impact_sound": self.impact_sound_edit.text().strip(),
            "shoot_sounds": self.shoot_sounds_edit.text().strip(),
            "shoot_silenced_sounds": self.shoot_silenced_sounds_edit.text().strip(),
            "dryfire_sounds": self.dryfire_sounds_edit.text().strip(),
        }

    def save_current_form(self):
        if not self.processing_data:
            return
        idx = self.processing_data["current_index"]
        if idx < 0 or idx >= len(self.processing_data.get("sticker_states", [])):
            return
        self.processing_data["sticker_states"][idx] = self.current_form_state()

    def load_form_state(self, idx):
        image_info = self.processing_data["images"][idx]
        return self.processing_data["sticker_states"][idx] or self.default_state_for_image(image_info)

    def show_current_image(self):
        idx = self.processing_data["current_index"]
        total = len(self.processing_data["images"])
        if idx < 0 or idx >= total:
            return
        image_info = self.processing_data["images"][idx]

        self.header_label.setText(f"Editing Sticker {idx + 1} of {total}")
        self.sticker_gallery.blockSignals(True)
        self.sticker_gallery.setCurrentRow(idx)
        self.sticker_gallery.blockSignals(False)
        for index, cell in enumerate(self.thumbnail_cells):
            cell.set_selected(index == idx, animated=not self.reduced_animations_enabled)

        # Stop any previous media
        self.gif_movie.stop()
        self.image_preview.setMovie(None)

        if image_info["path"].lower().endswith('.gif'):
            self.gif_movie.setFileName(image_info["path"])
            if self.autoplay_gifs_enabled:
                self.gif_movie.start()
            else:
                self.gif_movie.jumpToFrame(0)
                pixmap = self.gif_movie.currentPixmap()
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(self.image_preview.size() * 0.95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.image_preview.setPixmap(scaled_pixmap)
        else:
            pixmap = QPixmap(image_info["path"])
            if pixmap.isNull():
                self.image_preview.setText("Cannot preview this image format :(")
            else:
                scaled_pixmap = pixmap.scaled(self.image_preview.size() * 0.95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_preview.setPixmap(scaled_pixmap)

        state = self.load_form_state(idx)
        self.print_name_edit.setText(state["print_name"])
        self.compact_name_edit.setText(state["compact_name_input"])
        self.desc_edit.setText(state["description"])
        self.subfolder_edit.setText(state["subfolder"])
        self.install_sound_edit.setText(state.get("install_sound", ""))
        self.uninstall_sound_edit.setText(state.get("uninstall_sound", ""))
        self.impact_sound_edit.setText(state.get("impact_sound", ""))
        self.shoot_sounds_edit.setText(state.get("shoot_sounds", state.get("shoot_outdoor_sounds", "")))
        self.shoot_silenced_sounds_edit.setText(
            state.get("shoot_silenced_sounds", state.get("shoot_silenced_outdoor_sounds", ""))
        )
        self.dryfire_sounds_edit.setText(state.get("dryfire_sounds", ""))
        self.update_output_tree()
        # Auto-focus on display name for quick editing
        self.print_name_edit.setFocus()
        self.print_name_edit.selectAll()

        # Update back button based on current index
        if idx == 0:
            self.back_button.setText("< Back")
            self.back_button.setToolTip("Return to the setup screen")
        else:
            self.back_button.setText("< Previous Sticker")
            self.back_button.setToolTip("Go back to the previous sticker")

        if idx == total - 1:
            self.next_button.setText("Create Pack")
        else:
            self.next_button.setText("Next Sticker >")

    def next_image(self):
        idx = self.processing_data["current_index"]
        total = len(self.processing_data["images"])
        if idx < 0 or idx >= total:
            return

        print_name = self.print_name_edit.text().strip()
        if not print_name:
            QMessageBox.warning(self, "Missing Name", "Each sticker needs an in-game name before the pack can be created.")
            self.print_name_edit.setFocus()
            self.print_name_edit.selectAll()
            return

        user_compact_name = self.compact_name_edit.text().strip()
        if user_compact_name:
             compact_name = core.sanitize_for_filename(user_compact_name, strict=False)
        else:
             compact_name = core.sanitize_for_filename(print_name, strict=True)

        existing_names = self.compact_names_by_index()
        if compact_name in {
            name for index, name in existing_names.items() if index != idx
        }:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Duplicate Material Name")
            msg_box.setText(
                f"The material name '{compact_name}' is already in use.\n\n"
                "Choose a different material name before continuing."
            )
            
            laugh_path = self.get_asset_path('laugh.png')
            if os.path.exists(laugh_path):
                pixmap = QPixmap(laugh_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                msg_box.setIconPixmap(pixmap)
            else:
                msg_box.setIcon(QMessageBox.Warning)
            
            msg_box.exec()
            if user_compact_name:
                self.compact_name_edit.setFocus()
                self.compact_name_edit.selectAll()
            else:
                self.print_name_edit.setFocus()
                self.print_name_edit.selectAll()
            return

        self.processing_data["sticker_states"][idx] = self.current_form_state()
        self._subfolder_default_text = self.subfolder_edit.text().strip()

        if idx >= total - 1:
            self.finish_creation()
            return

        self.processing_data["current_index"] = idx + 1
        self.show_current_image()

    def compact_names_by_index(self):
        compact_names = {}
        for index, image_info in enumerate(self.processing_data["images"]):
            state = self.processing_data["sticker_states"][index] or self.default_state_for_image(image_info)
            print_name = state["print_name"]
            compact_input = state["compact_name_input"]
            compact_names[index] = (
                core.sanitize_for_filename(compact_input, strict=False)
                if compact_input
                else core.sanitize_for_filename(print_name, strict=True)
            )
        return compact_names

    def build_processed_info(self):
        processed_info = []
        compact_names = self.compact_names_by_index()
        for index, image_info in enumerate(self.processing_data["images"]):
            state = self.processing_data["sticker_states"][index] or self.default_state_for_image(image_info)
            processed_info.append({
                **image_info,
                "print_name": state["print_name"],
                "description": core.remove_emojis(state["description"]),
                "compact_name": compact_names[index],
                "subfolder": state["subfolder"],
                "install_sound": state.get("install_sound", ""),
                "uninstall_sound": state.get("uninstall_sound", ""),
                "impact_sound": state.get("impact_sound", ""),
                "shoot_sounds": state.get("shoot_sounds", state.get("shoot_outdoor_sounds", "")),
                "shoot_silenced_sounds": state.get(
                    "shoot_silenced_sounds",
                    state.get("shoot_silenced_outdoor_sounds", ""),
                ),
                "dryfire_sounds": state.get("dryfire_sounds", ""),
                "type": "animated" if image_info["path"].lower().endswith('.gif') else "static",
            })
        return processed_info

    def finish_creation(self):
        self.processing_data["processed_info"] = self.build_processed_info()
        self.details_scroll.setVisible(False)
        self.output_tree_frame.setVisible(False)
        self.button_frame.setVisible(False)
        self.progress_frame.setVisible(True)
        self.progress_bar.setMaximum(len(self.processing_data["images"]))

        self.worker = Worker(
            self.processing_data["output_dir"],
            self.processing_data["pack_name"],
            self.processing_data["processed_info"]
        )
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_creation_finished)
        self.worker.warning.connect(self.on_creation_warning)
        self.worker.error.connect(self.on_creation_error)
        self.worker.close.connect(self.on_worker_close)
        
        self.worker_thread.started.connect(self.worker.run)
        self.worker_thread.start()

    def update_progress(self, value, text, image_path):
        total = self.progress_bar.maximum()
        self.progress_bar.setValue(value)
        # Update label with percentage
        if total > 0:
            percentage = int((value / total) * 100)
            self.progress_label.setText(f"{text} ({percentage}%)")
        else:
            self.progress_label.setText(text)
        # Display the image being processed
        if image_path:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.image_preview.size() * 0.95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_preview.setPixmap(scaled_pixmap)
            else:
                self.image_preview.setText("Processing...")
        else:
            self.image_preview.setText("Processing...")

    def on_creation_finished(self, pack_name):
        # --- QOL: Add button to open folder on success ---
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Success")
        msg_box.setText(f"Successfully created the '{pack_name}' sticker pack!")
        msg_box.setInformativeText("The addon files are ready.")
        
        open_folder_button = msg_box.addButton("Open Addon Folder", QMessageBox.ActionRole)
        close_button = msg_box.addButton("Close", QMessageBox.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == open_folder_button:
            # Reconstruct the addon path
            addon_root = os.path.join(self.processing_data["output_dir"], f"arc9_{pack_name}_stickers")
            QDesktopServices.openUrl(QUrl.fromLocalFile(addon_root))

    def on_creation_warning(self, message):
        QMessageBox.warning(self, "Warning", message)

    def on_creation_error(self, error_msg):
        QMessageBox.critical(self, "An Error Occurred", error_msg)

    def on_worker_close(self):
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.worker_thread = None
        self.worker = None
        self.back_to_setup()

    def handle_back_action(self):
        """Handle back button - go to previous image if not first, otherwise go to setup."""
        idx = self.processing_data.get("current_index", 0)
        
        if idx > 0:
            # Go back to previous image
            self.save_current_form()
            self.processing_data["current_index"] -= 1
            self.show_current_image()
        else:
            # Go back to setup (first image)
            self.back_to_setup()

    def back_to_setup(self):
        self.gif_movie.stop()
        if self.worker:
            self.worker.is_running = False # Signal worker to stop
        self.switch_view(self.setup_widget)
        # Reset processing widget state
        self.details_scroll.setVisible(True)
        self.apply_output_tree_visibility()
        self.button_frame.setVisible(True)
        self.progress_frame.setVisible(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Initializing...")

    def resizeEvent(self, event):
        """Handle window resize to update background label size"""
        super().resizeEvent(event)
        if hasattr(self, 'bg_label') and self.bg_label.pixmap() and not self.bg_label.pixmap().isNull():
            # Update label height to match window height
            current_width = self.bg_label.width()
            self.bg_label.resize(current_width, self.height())

    def closeEvent(self, event):
        self.save_settings()
        if self.update_check_thread:
            self.update_check_thread.quit()
            self.update_check_thread.wait()
        self.back_to_setup() # Stop worker thread if running
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = StickerCreatorGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
