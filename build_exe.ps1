# Genera dist/Tablero30Dias.exe con PyInstaller.
# Uso: clic derecho > Ejecutar con PowerShell (o .\build_exe.ps1)
$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $appDir
pip install -r requirements.txt
pyinstaller --noconfirm --noconsole --onefile --name Tablero30Dias main.py
Write-Host ""
Write-Host "Listo: $appDir\dist\Tablero30Dias.exe"
