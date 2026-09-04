$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $root "scripts\start_all.cmd"
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw "Launcher not found: $launcher"
}

$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "Mongolian Voice Assistant.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $root
$shortcut.Description = "Start the local Mongolian Voice Assistant"
$shortcut.Save()

Write-Host "Installed current-user auto-start: $shortcutPath"
Write-Host "No administrator access is required."
