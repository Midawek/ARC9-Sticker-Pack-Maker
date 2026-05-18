@echo off
cd /d "%~dp0.."
echo Building GUI version...
python -m PyInstaller --onefile --windowed -i assets/logo.ico --name "ARC9StickerPackMaker++_Gui" --paths src --paths vendor/vtflib_wrapper/src --add-data "src/arc9_sticker_pack_maker;arc9_sticker_pack_maker" --add-data "vendor/vtflib_wrapper/src/vtflib;vendor/vtflib_wrapper/src/vtflib" --add-data "vendor/libs;vendor/libs" --add-data "assets;assets" --noconfirm run_gui.py

echo Building CLI version...
python -m PyInstaller --onefile --console -i assets/logo.ico --name "ARC9StickerPackMaker++_CLI" --paths src --paths vendor/vtflib_wrapper/src --add-data "src/arc9_sticker_pack_maker;arc9_sticker_pack_maker" --add-data "vendor/vtflib_wrapper/src/vtflib;vendor/vtflib_wrapper/src/vtflib" --add-data "vendor/libs;vendor/libs" --noconfirm run_cli.py

echo Build complete! Check the 'dist' folder.
pause
