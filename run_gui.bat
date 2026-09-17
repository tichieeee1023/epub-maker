@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    ".venv\Scripts\pythonw.exe" gui.py
) else (
    pythonw gui.py
)
