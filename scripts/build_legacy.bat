@echo off
cls
echo ===========================================
echo  Building ARC9 Sticker Pack Maker++
echo ===========================================
echo.

echo [1/2] Building GUI version (ARC9StickerPackMaker++_Gui.exe)...
echo.

py -m PyInstaller --onefile --windowed ^
    -i="assets\logo.ico" ^
    --name "ARC9StickerPackMaker++_Gui" ^
    --add-data "arc9_sticker_creator.py;." ^
    --add-data "note.txt;." ^
    --add-data "libs;libs" ^
    --add-data "assets;assets" ^
    --hidden-import=PySide6.QtSvg ^
    arc9_sticker_creator_gui.py

if %errorlevel% neq 0 (
    echo.
    echo ==========================================================
    echo  ERROR: Failed to build the GUI version.
    echo  PyInstaller exited with error code %errorlevel%.
    echo  Please check the output above for more details.
    echo ==========================================================
    pause
    exit /b %errorlevel%
)

echo.
echo GUI version built successfully!
echo.
echo ===========================================
echo.

echo [2/2] Building CLI version (ARC9StickerPackMaker++_CLI.exe)...
echo.

py -m PyInstaller --onefile --console ^
    -i="assets\logo.ico" ^
    --name "ARC9StickerPackMaker++_CLI" ^
    --add-data "note.txt;." ^
    --add-data "libs;libs" ^
    arc9_sticker_creator.py

if %errorlevel% neq 0 (
    echo.
    echo ==========================================================
    echo  ERROR: Failed to build the CLI version.
    echo  PyInstaller exited with error code %errorlevel%.
    echo  Please check the output above for more details.
    echo ==========================================================
    pause
    exit /b %errorlevel%
)

echo.
echo CLI version built successfully!
echo.
echo ===========================================
echo  Build process complete!
echo  You can find the executables in the 'dist' folder.
echo ===========================================
echo.
pause
