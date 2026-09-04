[CmdletBinding()]
param(
    [switch]$Check
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
$vite = Join-Path $root "frontend\node_modules\.bin\vite.cmd"
$browserHelper = Join-Path $root "scripts\open_control_panel.ps1"

function Test-ListeningPort([int]$Port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found: $python"
}
if (-not (Test-Path -LiteralPath $vite -PathType Leaf)) {
    throw "Frontend dependencies not found: $vite"
}
if ($Check) {
    Write-Output "[ok] $python"
    Write-Output "[ok] $vite"
    exit 0
}

if (-not (Test-ListeningPort 8000)) {
    Start-Process -FilePath $python -ArgumentList @("-m", "src.main", "api") -WorkingDirectory $root -WindowStyle Hidden
}
if (-not (Test-ListeningPort 5173)) {
    Start-Process -FilePath $vite -ArgumentList @("--host", "127.0.0.1", "--strictPort") -WorkingDirectory (Join-Path $root "frontend") -WindowStyle Hidden
}

# pythonw keeps the tray-only companion out of the taskbar/Alt-Tab list. Its
# pystray icon remains visible in the notification area as the running signal.
if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) {
    $pythonw = $python
}
Start-Process -FilePath $pythonw -ArgumentList @("-m", "src.main", "desktop") -WorkingDirectory $root -WindowStyle Hidden
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", $browserHelper) -WorkingDirectory $root -WindowStyle Hidden
