# Crea accesos directos en Escritorio y (opcional) Inicio con Windows.
# Uso: clic derecho > Ejecutar con PowerShell
$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $appDir "dist\Tablero30Dias.exe"

# Si existe el .exe se usa directo; si no, se usa Python.
if (Test-Path $exe) {
    $target = $exe
    $usarPython = $false
} else {
    $pythonw = Join-Path (Split-Path (Get-Command python.exe).Source) "pythonw.exe"
    if (-not (Test-Path $pythonw)) { $pythonw = (Get-Command python.exe).Source }
    $target = $pythonw
    $usarPython = $true
}

$Wsh = New-Object -ComObject WScript.Shell
$escritorio = [Environment]::GetFolderPath("Desktop")
$startup = [Environment]::GetFolderPath("Startup")

function Nuevo-Acceso($carpeta, $nombre, $args) {
    $lnk = Join-Path $carpeta "$nombre.lnk"
    $sc = $Wsh.CreateShortcut($lnk)
    if ($usarPython) {
        $sc.TargetPath = $target
        $sc.Arguments = "`"$appDir\main.py`" $args"
    } else {
        $sc.TargetPath = $target
        $sc.Arguments = $args
    }
    $sc.WorkingDirectory = $appDir
    $sc.IconLocation = "$env:SystemRoot\System32\shell32.dll,21"
    $sc.Save()
    Write-Host "Creado: $lnk"
}

Nuevo-Acceso $escritorio "Tablero 30 dias" ""
Nuevo-Acceso $escritorio "Tablero Widget" "--widget"
Nuevo-Acceso $startup "Tablero Widget" "--widget"
Write-Host "Listo. El widget arrancara con Windows. Quitalo de shell:startup si no lo quieres."
pause
