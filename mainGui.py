import sys
import os
import ctypes
import threading
import queue
import json

# --- Determine the base path for bundled assets and modules ---
if getattr(sys, 'frozen', False):
    BASE_PATH = sys._MEIPASS
    OUTPUT_BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_BASE_PATH = BASE_PATH

# --- Consolidate sys.path modification here ---
if BASE_PATH not in sys.path:
    sys.path.insert(0, BASE_PATH)
LIBS_PATH = os.path.join(BASE_PATH, 'libs')
if LIBS_PATH not in sys.path:
    sys.path.insert(0, LIBS_PATH)

# --- Dependency Management ---
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox,
        QStackedWidget, QFrame, QCheckBox, QProgressBar, QGraphicsOpacityEffect)
    from PySide6.QtGui import QPixmap, QFontDatabase, QFont, QMovie, QIcon, QColor, QPainter, QDesktopServices, QPainterPath
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtCore import Qt, QThread, Signal, QObject, QPropertyAnimation, QEasingCurve, Property, QSequentialAnimationGroup, QPoint, QSettings, QUrl, QSize
except ImportError:
    print("ERROR: PySide6 is not installed. Please install it using: pip install PySide6")
    sys.exit(1)


try:
    import arc9_sticker_creator as core
except ImportError as e:
    # Use QMessageBox if QApplication has been successfully imported and initialized
    if 'QApplication' in locals() or 'QApplication' in globals():
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        QMessageBox.critical(None, "Import Error", f"Could not import core script 'arc9_sticker_creator.py'.\nError: {e}\nPlease make sure it's in the same directory.")
    else:
        print(f"ERROR: Could not import core script 'arc9_sticker_creator.py'.\nError: {e}\nPlease make sure it's in the same directory.")
    sys.exit(1)

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
                    core.create_lua_script(self.output_dir, self.pack_name, successful_images)
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

# --- Main Application Window ---
class StickerCreatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARC9 Sticker Pack Maker++")
        self.setFixedSize(600, 850)
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
        background_enabled = self.settings.value("background_enabled", True, type=bool)

        self.bg_checkbox.setChecked(background_enabled)
        # Only toggle if background exists, otherwise it's already set up correctly
        if hasattr(self, 'bg_label') and self.bg_label.pixmap() and not self.bg_label.pixmap().isNull():
            self.toggle_background(background_enabled)

        # --- QOL: Load last used paths ---
        image_folder = self.settings.value("image_folder_path", "", type=str)
        output_folder = self.settings.value("output_folder_path", OUTPUT_BASE_PATH, type=str)
        if image_folder and os.path.isdir(image_folder):
            self.img_folder_path.setText(image_folder)
        if output_folder and os.path.isdir(output_folder):
            self.out_folder_path.setText(output_folder)

        self._subfolder_default_text = self.settings.value("subfolder_default_text", "", type=str)

    def save_settings(self):
        self.settings.setValue("background_enabled", self.bg_checkbox.isChecked())
        # --- QOL: Save last used paths ---
        self.settings.setValue("image_folder_path", self.img_folder_path.text())
        self.settings.setValue("output_folder_path", self.out_folder_path.text())
        self.settings.setValue("subfolder_default_text", self._subfolder_default_text)

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
        settings_icon_path = self.get_asset_path('settings.svg')
        settings_label = QLabel()
        if os.path.exists(settings_icon_path):
            settings_icon = QIcon(settings_icon_path)
            settings_pixmap = settings_icon.pixmap(32, 32)
            if not settings_pixmap.isNull():
                # Recolor icon to light color for visibility on dark background
                # Get the mask from the pixmap (non-transparent areas)
                mask = settings_pixmap.mask()
                if mask.isNull():
                    # If no mask, create one from non-transparent pixels
                    mask = QPixmap(settings_pixmap.size())
                    mask.fill(Qt.black)
                    temp_painter = QPainter(mask)
                    temp_painter.setCompositionMode(QPainter.CompositionMode_Source)
                    temp_painter.drawPixmap(0, 0, settings_pixmap)
                    temp_painter.end()
                
                # Create colored pixmap with light color
                colored_pixmap = QPixmap(settings_pixmap.size())
                colored_pixmap.fill(QColor("#e0e0e0"))  # Light gray color
                colored_pixmap.setMask(mask)
                settings_label.setPixmap(colored_pixmap)
            else:
                # Fallback if pixmap creation fails
                settings_label.setText("⚙")
                settings_label.setStyleSheet("color: #e0e0e0; font-size: 24px;")
        else:
            # Fallback: use text if icon doesn't exist
            settings_label.setText("⚙")
            settings_label.setStyleSheet("color: #e0e0e0; font-size: 24px;")
        settings_label.setFixedSize(40, 40)
        settings_label.setAlignment(Qt.AlignCenter)
        settings_label.setCursor(Qt.PointingHandCursor)
        settings_label.mousePressEvent = lambda e: self.show_settings_widget()
        # Set base stylesheet first, then append hover styles
        base_style = "QLabel { background-color: transparent; border: none; }"
        hover_style = "QLabel:hover { background-color: rgba(255, 255, 255, 0.1); border-radius: 4px; }"
        settings_label.setStyleSheet(base_style + hover_style)
        top_layout.addWidget(settings_label)
        layout.addLayout(top_layout)

        # Banner
        banner_label = QLabel()
        pixmap = QPixmap(self.get_asset_path('banner.png'))
        if not pixmap.isNull():
            banner_label.setPixmap(pixmap.scaled(550, 350, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        banner_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(banner_label)
        layout.addSpacing(20)

        # Form
        form_frame = QFrame()
        form_frame.setObjectName("formFrame")
        form_layout = QVBoxLayout(form_frame)

        # Image Folder
        img_folder_layout = QHBoxLayout()
        img_folder_label = QLabel("Image Folder:")
        img_folder_label.setMinimumWidth(120)
        self.img_folder_path = DropLineEdit()
        self.img_folder_path.setPlaceholderText("Select or drop a folder with your images...")
        self.img_folder_path.setReadOnly(True)
        self.img_folder_path.setToolTip("Select the folder containing your sticker images (PNG, JPG, GIF supported)")
        img_folder_btn = QPushButton("Browse...")
        img_folder_btn.clicked.connect(self.browse_image_folder)
        img_folder_btn.setToolTip("Click to browse for image folder")
        img_folder_layout.addWidget(img_folder_label)
        img_folder_layout.addWidget(self.img_folder_path)
        img_folder_layout.addWidget(img_folder_btn)
        form_layout.addLayout(img_folder_layout)
        form_layout.addSpacing(10)

        # Output Folder
        out_folder_layout = QHBoxLayout()
        out_folder_label = QLabel("Output Folder:")
        out_folder_label.setMinimumWidth(120)
        self.out_folder_path = DropLineEdit(OUTPUT_BASE_PATH)
        self.out_folder_path.setReadOnly(True)
        self.out_folder_path.setToolTip("Where the generated addon will be saved")
        out_folder_btn = QPushButton("Browse...")
        out_folder_btn.clicked.connect(self.browse_output_folder)
        out_folder_btn.setToolTip("Click to change output location")
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
        self.pack_name.setPlaceholderText("Enter a cute name for your pack...")
        self.pack_name.setToolTip("The name of your sticker pack (emojis will be removed automatically, keep it short and sweet)")
        self.pack_name.returnPressed.connect(self.start_processing)  # Enter key support
        pack_name_layout.addWidget(pack_name_label)
        pack_name_layout.addWidget(self.pack_name)
        form_layout.addLayout(pack_name_layout)
        
        layout.addWidget(form_frame)
        layout.addStretch()

        # Start Button
        start_button = AnimatedButton("Start Processing ")
        start_button.clicked.connect(self.start_processing)
        start_button.setToolTip("Start processing your images (or press Enter after filling pack name)")
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

        title_label = QLabel("Settings")
        title_label.setObjectName("header")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        layout.addSpacing(20)

        form_frame = QFrame()
        form_frame.setObjectName("formFrame")
        form_layout = QVBoxLayout(form_frame)

        # Background Toggle
        self.bg_checkbox = QCheckBox("Enable Scrolling Background")
        self.bg_checkbox.setChecked(True)
        self.bg_checkbox.stateChanged.connect(self.toggle_background)
        form_layout.addWidget(self.bg_checkbox)

        layout.addWidget(form_frame)
        layout.addStretch()
        
        # GitHub Link
        github_label = QLabel()
        github_icon_path = self.get_asset_path('github.svg')
        if os.path.exists(github_icon_path):
            github_icon = QIcon(github_icon_path)
            github_pixmap = github_icon.pixmap(64, 64)
            if not github_pixmap.isNull():
                github_label.setPixmap(github_pixmap)
        github_label.setAlignment(Qt.AlignCenter)
        github_label.setCursor(Qt.PointingHandCursor)
        github_label.mousePressEvent = self.open_github
        layout.addWidget(github_label)

        back_button = QPushButton("< Back to Main Menu")
        back_button.clicked.connect(self.show_setup_widget)
        layout.addWidget(back_button, alignment=Qt.AlignCenter)

        return widget

    def switch_view(self, new_widget):
        """ Animates the transition between stacked widget pages. """
        current_widget = self.stacked_widget.currentWidget()
        if current_widget is new_widget:
            return

        # Fade out current widget
        self.fade_out_animation = QPropertyAnimation(current_widget.graphicsEffect(), b"opacity")
        self.fade_out_animation.setDuration(150)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.InQuad)
        
        # After fade-out, switch widget and fade in
        def on_finished():
            current_widget.graphicsEffect().setOpacity(1.0) # Reset for next time
            self.stacked_widget.setCurrentWidget(new_widget)
            new_widget.graphicsEffect().setOpacity(0.0) # Start transparent

            self.fade_in_animation = QPropertyAnimation(new_widget.graphicsEffect(), b"opacity")
            self.fade_in_animation.setDuration(150)
            self.fade_in_animation.setStartValue(0.0)
            self.fade_in_animation.setEndValue(1.0)
            self.fade_in_animation.setEasingCurve(QEasingCurve.OutQuad)
            self.fade_in_animation.start()

        self.fade_out_animation.finished.connect(on_finished)
        self.fade_out_animation.start()

    def show_settings_widget(self):
        self.switch_view(self.settings_widget)

    def show_setup_widget(self):
        self.switch_view(self.setup_widget)

    def open_github(self, event):
        QDesktopServices.openUrl(QUrl("https://github.com/Midawek/ARC9-Sticker-Pack-Maker"))

    def create_processing_widget(self):
        widget = QWidget()
        self.processing_layout = QVBoxLayout(widget)
        self.processing_layout.setContentsMargins(20, 20, 20, 20)

        self.header_label = QLabel("Processing Image 1 of N")
        self.header_label.setObjectName("header")
        self.header_label.setAlignment(Qt.AlignCenter)
        self.processing_layout.addWidget(self.header_label)

        self.image_preview = QLabel("Image preview will appear here! ✨")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumSize(550, 500)
        self.image_preview.setObjectName("imagePreview")
        self.processing_layout.addWidget(self.image_preview)
        self.gif_movie = QMovie(self)
        self.gif_movie.frameChanged.connect(self.update_gif_frame)

        # Details Frame
        self.details_frame = QFrame()
        self.details_frame.setObjectName("formFrame")
        details_layout = QVBoxLayout(self.details_frame)

        # Display Name
        name_layout = QHBoxLayout()
        name_label = QLabel("Display Name:")
        name_label.setMinimumWidth(120)
        self.print_name_edit = QLineEdit()
        self.print_name_edit.setToolTip("The name that will appear in-game for this sticker")
        self.print_name_edit.returnPressed.connect(self.next_image)  # Enter key support
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.print_name_edit)
        details_layout.addLayout(name_layout)
        details_layout.addSpacing(8)

        # Description
        desc_layout = QHBoxLayout()
        desc_label = QLabel("Description:")
        desc_label.setMinimumWidth(120)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Optional description for this sticker...")
        self.desc_edit.setToolTip("Optional description text (supports multi-line)")
        desc_layout.addWidget(desc_label)
        desc_layout.addWidget(self.desc_edit)
        details_layout.addLayout(desc_layout)
        details_layout.addSpacing(8)

        # Subfolder
        subfolder_layout = QHBoxLayout()
        subfolder_label = QLabel("Subfolder:")
        subfolder_label.setMinimumWidth(120)
        self.subfolder_edit = QLineEdit()
        self.subfolder_edit.setPlaceholderText("e.g., Characters/Cute (Optional)")
        self.subfolder_edit.setToolTip("Optional subfolder path to organize stickers (e.g., Characters/Cute)")
        self.subfolder_edit.setText(self._subfolder_default_text) # Set initial text here
        subfolder_layout.addWidget(subfolder_label)
        subfolder_layout.addWidget(self.subfolder_edit)
        details_layout.addLayout(subfolder_layout)
        self.processing_layout.addWidget(self.details_frame)

        # Progress Frame (initially hidden)
        self.progress_frame = QFrame()
        progress_layout = QVBoxLayout(self.progress_frame)
        self.progress_label = QLabel("Initializing...")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        self.processing_layout.addWidget(self.progress_frame)
        self.progress_frame.setVisible(False)

        self.processing_layout.addStretch()

        # Button Frame
        self.button_frame = QFrame()
        button_layout = QHBoxLayout(self.button_frame)
        button_layout.setContentsMargins(0,0,0,0)
        self.back_button = QPushButton("< Back to Setup")
        self.back_button.clicked.connect(self.handle_back_action)
        self.back_button.setToolTip("Return to the setup screen")
        self.next_button = AnimatedButton("Next Image >")
        self.next_button.clicked.connect(self.next_image)
        self.next_button.setToolTip("Save current image and move to next (or press Enter)")
        button_layout.addWidget(self.back_button)
        button_layout.addStretch()
        button_layout.addWidget(self.next_button)
        self.processing_layout.addWidget(self.button_frame)

        return widget

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
            QLabel {{
                padding: 5px;
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
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder", dir=OUTPUT_BASE_PATH)
        if folder:
            self.img_folder_path.setText(folder)

    def browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", dir=OUTPUT_BASE_PATH)
        if folder:
            self.out_folder_path.setText(folder)

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
        images_to_process = []
        try:
            for filename in sorted(os.listdir(image_folder)):
                file_path = os.path.join(image_folder, filename)
                if os.path.isdir(file_path):
                    continue
                # Use a more reliable method to check for valid images
                pixmap = QPixmap(file_path)
                if pixmap.isNull():
                    continue  # Skip files that Qt can't read

                original_name = os.path.splitext(filename)[0]
                images_to_process.append({"path": file_path, "original_name": original_name})
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
            "pack_name": core.remove_emojis(pack_name),
            "output_dir": output_dir,
            "images": images_to_process,
            "processed_info": [],
            "current_index": 0
        }
        
        self.switch_view(self.processing_widget)
        self.show_current_image()

    def show_current_image(self):
        idx = self.processing_data["current_index"]
        total = len(self.processing_data["images"])
        image_info = self.processing_data["images"][idx]

        self.header_label.setText(f"Processing Image {idx + 1} of {total}")

        # Stop any previous media
        self.gif_movie.stop()
        self.image_preview.setMovie(None)

        if image_info["path"].lower().endswith('.gif'):
            self.gif_movie.setFileName(image_info["path"])
            self.gif_movie.start()
        else:
            pixmap = QPixmap(image_info["path"])
            if pixmap.isNull():
                self.image_preview.setText("Cannot preview this image format :(")
            else:
                scaled_pixmap = pixmap.scaled(self.image_preview.size() * 0.95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_preview.setPixmap(scaled_pixmap)

        self.print_name_edit.setText(image_info["original_name"].replace('_', ' ').title())
        self.desc_edit.setText("")
        self.subfolder_edit.setText("")
        # Auto-focus on display name for quick editing
        self.print_name_edit.setFocus()
        self.print_name_edit.selectAll()

        # Update back button based on current index
        if idx == 0:
            self.back_button.setText("< Back to Setup")
            self.back_button.setToolTip("Return to the setup screen")
        else:
            self.back_button.setText("< Previous Image")
            self.back_button.setToolTip("Go back to the previous image")

        if idx == total - 1:
            self.next_button.setText("Finish & Create Pack ✨")
        else:
            self.next_button.setText("Next Image >")

    def next_image(self):
        idx = self.processing_data["current_index"]
        total = len(self.processing_data["images"])
        current_image_info = self.processing_data["images"][idx]

        print_name = self.print_name_edit.text().strip()
        if not print_name:
            QMessageBox.warning(self, "Validation Error", "Display Name cannot be empty.\n\nPlease enter a name for this sticker.")
            self.print_name_edit.setFocus()
            self.print_name_edit.selectAll()
            return

        self.processing_data["processed_info"].append({
            **current_image_info,
            "print_name": print_name,
            "description": core.remove_emojis(self.desc_edit.text()),
            "compact_name": core.sanitize_for_filename(print_name),
            "subfolder": self.subfolder_edit.text().strip(),
            "type": "animated" if current_image_info["path"].lower().endswith('.gif') else "static"
        })

        self._subfolder_default_text = self.subfolder_edit.text().strip() # Update default for next sticker
        
        self.processing_data["current_index"] += 1
        if self.processing_data["current_index"] < total:
            self.show_current_image()
        else:
            self.finish_creation()

    def finish_creation(self):
        self.details_frame.setVisible(False)
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
        msg_box.setInformativeText("Thank you for using the tool! Meow! :3")
        
        open_folder_button = msg_box.addButton("Open Addon Folder", QMessageBox.ActionRole)
        close_button = msg_box.addButton("Close", QMessageBox.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == open_folder_button:
            # Reconstruct the addon path
            addon_root = os.path.join(self.processing_data["output_dir"], f"arc9_{pack_name}_stickers")
            QDesktopServices.openUrl(QUrl.fromLocalFile(addon_root))

    def on_creation_warning(self, message):
        QMessageBox.warning(self, "Warning", f"{message}\n\nThank you for using the creator anyway!")

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
            self.processing_data["current_index"] -= 1
            # Remove the last processed info entry if it exists
            if self.processing_data["processed_info"]:
                self.processing_data["processed_info"].pop()
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
        self.details_frame.setVisible(True)
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
        self.back_to_setup() # Stop worker thread if running
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StickerCreatorGUI()
    window.show()
    sys.exit(app.exec())
