# Mongolian Voice Assistant

A local Windows voice assistant with Mongolian and English speech-to-text, text-to-speech, an optional NVIDIA NIM agent bridge, a browser control panel, and a global `Ctrl + Alt` dictation companion.

## What is included

- FastAPI API on loopback (`127.0.0.1:8000`)
- React/Vite control panel on `127.0.0.1:5173`
- Windows tray dictation companion with clipboard insertion
- Mongolian, English, and auto-detect dictation modes
- Persistent desktop language preference in `cache/desktop-preferences.json`
- Portable runtime paths resolved from the repository or `VOICE_ASSISTANT_ROOT`
- One-click startup and reversible current-user auto-start scripts

## Requirements

- Windows 10/11 x64
- Python 3.12
- Node.js 20 or newer
- A working microphone for desktop dictation
- NVIDIA GPU and CUDA-compatible PyTorch for the configured GPU STT/TTS paths; CPU fallback is available where configured
- NVIDIA API credentials only when using the `nvidia_nim` agent provider

## Quick start

Run these commands from the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
Push-Location frontend
npm install
Pop-Location
```

Review `config/config.yaml`. The STT setup routes Mongolian to `orgilj/moonshine-mn` and English to `Qwen/Qwen3-ASR-0.6B-hf`. Only the selected model is resident at a time. Download both when needed:

```powershell
.venv\Scripts\python.exe scripts\download_stt.py
.venv\Scripts\python.exe scripts\download_tts.py
```

The download scripts read the configured paths. They do not contain machine-specific drive letters.

Use the explicit language selector for reliable routing. Auto mode asks Qwen to identify supported languages and falls back to Moonshine when the result is not English.

Check the installation, then start all three local processes:

```powershell
scripts\start_all.cmd --check
scripts\start_all.cmd
```

The launcher opens separate windows for the API, browser UI, and desktop tray companion. Open the control panel at <http://127.0.0.1:5173/>.

## Configuration

Copy `.env.example` to `.env` and set private credentials there. To keep models, recordings, Hugging Face cache, and runtime cache outside the checkout, set:

```text
VOICE_ASSISTANT_ROOT=C:/Users/your-name/voice-assistant-data
```

Relative paths in `config/config.yaml` resolve under that root. Absolute paths remain absolute. The API rejects non-loopback bind hosts.

Useful commands:

```powershell
.venv\Scripts\python.exe -m src.main --help
.venv\Scripts\python.exe -m src.main status
.venv\Scripts\python.exe -m src.main devices
.venv\Scripts\python.exe -m src.main api
.venv\Scripts\python.exe -m src.main desktop
```

## Auto-start at sign-in

Install a current-user Startup-folder shortcut:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-autostart.ps1
```

Remove it later with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall-autostart.ps1
```

The installer is idempotent, uses the launcher beside the repository, and does not require administrator access.

## Logs and runtime data

Runtime data is intentionally ignored by Git:

- `logs/` — application logs
- `cache/` — desktop status, preferences, and temporary API files
- `recordings/` — optional saved recordings
- `models/` and `huggingface/` — downloaded model data

## Development checks

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q src scripts
Push-Location frontend
npm test
npm run build
Pop-Location
```

GitHub Actions runs the Python and frontend checks independently. CI installs dependencies but does not download model weights, require a GPU, or call external inference services.
