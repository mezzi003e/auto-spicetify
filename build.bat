@echo off
python -m pip install --upgrade pyinstaller
python -m PyInstaller --onefile --noconsole --icon assets\icon.ico --name auto_spicetify auto_spicetify.py
echo.
echo Done. Your executable is in dist\auto_spicetify.exe
pause
