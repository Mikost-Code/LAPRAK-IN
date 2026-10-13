@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  if not exist "frontend\dist\index.html" (
    echo Antarmuka React belum dibangun.
    echo Jalankan npm install lalu npm run build di folder frontend.
    pause
    exit /b 1
  )
  start "" ".venv\Scripts\pythonw.exe" -m laprak
) else (
  echo Virtual environment belum tersedia. Ikuti langkah instalasi pada README.md.
  pause
)
