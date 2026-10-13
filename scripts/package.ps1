$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$projectPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
& $projectPython -m PyInstaller --noconfirm --windowed --name Laprak --paths . --add-data 'laprak/assets;laprak/assets' --hidden-import keyring.backends.Windows --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineQuick --exclude-module tkinter run_laprak.py
if ($LASTEXITCODE -ne 0) { throw 'Packaging gagal.' }
# The user-owned template is not bundled or redistributed automatically.
Copy-Item -LiteralPath (Join-Path $projectRoot 'README.md') -Destination (Join-Path $projectRoot 'dist/Laprak/README.md')
Write-Output 'Aplikasi portable: dist/Laprak/Laprak.exe. Distribusikan seluruh folder Laprak.'
