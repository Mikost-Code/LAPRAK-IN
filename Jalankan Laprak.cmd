@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m laprak
) else (
  echo Virtual environment belum tersedia. Ikuti langkah instalasi pada README.md.
  pause
)
