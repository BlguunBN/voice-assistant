$ErrorActionPreference = "Stop"

$controlPanelUrl = "http://127.0.0.1:5173/"

# Open only after the Vite server itself is listening. The API may take longer
# on a cold model load, but the control panel can show its own loading status.
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        Invoke-WebRequest -Uri $controlPanelUrl -UseBasicParsing -TimeoutSec 1 | Out-Null
        Start-Process $controlPanelUrl
        exit 0
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

Write-Warning "Voice Assistant could not start the control panel. Check the UI window."
exit 1
