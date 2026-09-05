# Windows setup guide

This guide installs the local voice assistant without assuming a fixed checkout path.

## 1. Install prerequisites

Install Python 3.12 and Node.js 20 or newer. If using GPU inference, install a compatible NVIDIA driver and confirm that the Python environment can import the configured CUDA build of PyTorch.

From the repository root:

```powershell
py -3.12 --version
node --version
npm --version
```

## 2. Create the Python environment

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The requirements file pins the CUDA 12.8 PyTorch wheels. Change that dependency set only if the machine needs a different supported PyTorch/CUDA combination.

## 3. Configure secrets and paths

```powershell
Copy-Item .env.example .env
```

Set `NVIDIA_API_KEY` and `NVIDIA_NIM_MODEL` only if the configured agent provider is `nvidia_nim`. Never commit `.env`.

The default `config/config.yaml` uses relative paths. They resolve from the checkout. For a separate data directory, add this to `.env`:

```text
VOICE_ASSISTANT_ROOT=C:/Users/your-name/voice-assistant-data
```

This relocates model, Hugging Face, recording, and runtime cache paths while leaving the source checkout portable.

## 4. Install the web UI

```powershell
Push-Location frontend
npm install
Pop-Location
```

The UI is a Vite development server. It calls the local API and stores device selections in browser local storage. The desktop dictation language is also persisted by the API so the tray companion and UI use the same setting.

## 5. Download models when needed

The configured Edge TTS provider does not require a local Mongolian TTS model. The single multilingual Whisper model serves every desktop language selection, so download it once:

```powershell
.venv\Scripts\python.exe scripts\download_stt.py
```

The legacy `--language mn|en|auto|all` options remain accepted but all select the same `openai/whisper-large-v3-turbo` snapshot at `D:/AI/models/stt/whisper-large-v3-turbo`. Runtime uses FP16 on CUDA when available; CUDA OOM unloads the GPU copy and retries on CPU.

For the configured local TTS backend only:

```powershell
.venv\Scripts\python.exe scripts\download_tts.py
```

## 6. Start the application

Validate dependencies first:

```powershell
scripts\start_all.cmd --check
```

Start the API, UI, and tray companion:

```powershell
scripts\start_all.cmd
```

Open <http://127.0.0.1:5173/>. The API documentation is at <http://127.0.0.1:8000/docs>.

The desktop companion listens for `Win + Alt`, records while the chord is held, sends the recording to `/stt`, and pastes the transcript into the focused application. The control panel's **Dictation language** selector supports `Монгол`, `English`, and `Auto detect`. The same rail shows the current companion state and the last detected language when auto-detect is used.

## 7. Optional sign-in auto-start

Install the current-user Startup shortcut:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-autostart.ps1
```

The shortcut targets `scripts\start_all.cmd` and uses the repository directory as its working directory. Re-running the installer updates the same shortcut. Remove it with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall-autostart.ps1
```

## Troubleshooting

- `start_all.cmd --check` reports the exact missing Python or frontend dependency path.
- API, model, and desktop logs are written under the configured `logs/` directory.
- If the UI says `Offline`, confirm that the API window is running and that `http://127.0.0.1:8000/health` responds.
- If the tray companion cannot start, verify that `pystray`, Pillow, `sounddevice`, and a usable microphone are installed.
- If model loading fails with a Windows paging-file error, increase the system paging-file size or configure a smaller model/CPU fallback before retrying.
- If the Startup shortcut is stale, run the uninstall script and then the install script again.
