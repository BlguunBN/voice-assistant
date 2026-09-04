$ErrorActionPreference = "Stop"

$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "Mongolian Voice Assistant.lnk"
if (Test-Path -LiteralPath $shortcutPath -PathType Leaf) {
    Remove-Item -LiteralPath $shortcutPath -Force
    Write-Host "Removed current-user auto-start: $shortcutPath"
} else {
    Write-Host "Auto-start shortcut was not installed."
}
