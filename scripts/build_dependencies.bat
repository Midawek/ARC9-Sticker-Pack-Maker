@echo off
echo "Downloading required libraries... Please wait."
python -m pip install --upgrade --target=./libs PySide6 pillow
echo "Dependencies have been bundled successfully!"
pause
