You are implementing a complete local Mongolian voice interface on my Windows 11 laptop.

Your job is to inspect my current environment, create the project, install all required dependencies, downloadconfigure the models, implement the code, run tests, debug failures, and leave me with a working system.

Do not only give me instructions. Perform the implementation yourself using terminal commands and file edits available to you.

## Hardware

Target machine

 Windows 11
 AMD Ryzen 7 6800H
 NVIDIA RTX 3050 Laptop GPU
 4 GB VRAM
 16 GB RAM
 Windows installed on `C`
 AI projectsmodels should be stored on `D`

Do not put large model files or Hugging Face caches on `C`.

## Main objective

Build a reusable local speech service supporting

1. Mongolian speech-to-text
2. Mongolian text-to-speech
3. Microphone input
4. Speaker output
5. Push-to-talk
6. Voice activity detection
7. Connection to an AI agentLLM
8. Fully local speech processing
9. Future HermesPilocal-agent integration
10. REST API for external programs

Target pipeline

```text
Microphone
    ↓
Voice Activity Detection
    ↓
Mongolian STT
    ↓
Mongolian text
    ↓
Agent  LLM bridge
    ↓
Mongolian response
    ↓
Mongolian TTS
    ↓
Speakers
```

## Models

### STT

Use

`Blgn94whisper-small-mn-v3`

Purpose

Mongolian Cyrillic speech recognition.

Prefer GPU inference on the RTX 3050.

Start with the normal Hugging Face Transformers implementation because compatibility is more important than optimization.

After baseline STT works correctly, evaluate converting it to CTranslate2faster-whisper if that provides materially lower latency or memory usage without breaking the Mongolian fine-tune.

Do not replace the Mongolian model with vanilla Whisper unless the selected model cannot be made to work.

### TTS

Use

`Bokhbatmongolian-vits-tts`

Purpose

Mongolian speech generation.

Expected files include

```text
best_model.pth
config.json
speakers.pth
```

Run TTS on CPU initially to preserve the 4 GB GPU for STT.

The model supports multiple speakers. Implement speaker discovery and configurable speaker selection.

## Storage

Everything large must be under

```text
DAI
```

Use this layout

```text
DAI
│
├── voice-assistant
│   ├── src
│   ├── config
│   ├── tests
│   ├── logs
│   ├── cache
│   └── .venv
│
├── models
│   ├── stt
│   │   └── whisper-small-mn-v3
│   │
│   └── tts
│       └── mongolian-vits-tts
│
├── huggingface
│   └── hub
│
└── recordings
    ├── input
    └── output
```

Set persistent Windows environment variables

```powershell
setx HF_HOME DAIhuggingface
setx HF_HUB_CACHE DAIhuggingfacehub
```

Also explicitly use `cache_dir` or local model paths where appropriate so downloads cannot silently fill the C drive.

Do not move CUDA, NVIDIA drivers, Windows system components, or unrelated installed software.

## Project structure

Create or adapt

```text
DAIvoice-assistant
│
├── src
│   ├── main.py
│   │
│   ├── audio
│   │   ├── __init__.py
│   │   ├── recorder.py
│   │   ├── player.py
│   │   └── vad.py
│   │
│   ├── stt
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── whisper_mn.py
│   │
│   ├── tts
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── vits_mn.py
│   │
│   ├── agent
│   │   ├── __init__.py
│   │   ├── bridge.py
│   │   └── echo_agent.py
│   │
│   ├── text
│   │   ├── __init__.py
│   │   └── normalizer.py
│   │
│   ├── api
│   │   ├── __init__.py
│   │   └── server.py
│   │
│   └── core
│       ├── __init__.py
│       ├── config.py
│       ├── pipeline.py
│       └── events.py
│
├── config
│   └── config.yaml
│
├── tests
├── requirements.txt
├── .gitignore
├── start.ps1
└── README.md
```

If any of these files already exist, inspect and extend them rather than recreating or overwriting working code unnecessarily.

## Implementation order

Follow this order strictly.

### Phase 1 — Environment

Create

```text
DAIvoice-assistant
```

Create the virtual environment at

```text
DAIvoice-assistant.venv
```

Install a CUDA-compatible PyTorch build appropriate for the currently installed NVIDIA driver.

Before installing CUDA-specific packages, inspect

```powershell
nvidia-smi
```

and verify PyTorch afterward

```python
import torch

print(torch.__version__)
print(torch.cuda.is_available())

if torch.cuda.is_available()
    print(torch.cuda.get_device_name(0))
    print(torch.cuda.get_device_properties(0).total_memory)
```

Do not blindly install incompatible CUDA builds.

### Phase 2 — STT baseline

Downloadconfigure

```text
Blgn94whisper-small-mn-v3
```

Implement

```python
class STTEngine
    def load(self)
        ...

    def transcribe(self, audio)
        ...

    def unload(self)
        ...
```

Support both

```text
cuda
cpu
```

Use CUDA when available.

Implement file transcription first.

Required CLI

```powershell
python -m src.main transcribe Dpathtest.wav
```

Return the recognized Mongolian Cyrillic text.

Do not proceed to microphone integration until WAV transcription works.

### Phase 3 — TTS baseline

Downloadconfigure

```text
Bokhbatmongolian-vits-tts
```

Store the model under

```text
DAImodelsttsmongolian-vits-tts
```

Implement

```python
class TTSEngine
    def load(self)
        ...

    def synthesize(self, text, speaker_id=None)
        ...

    def speak(self, text, speaker_id=None)
        ...

    def unload(self)
        ...
```

Run TTS on CPU initially.

Required CLI

```powershell
python -m src.main speak Сайн байна уу
```

The command must generate Mongolian speech and play it through the Windows default audio device.

Also support

```powershell
python -m src.main speak --output DAIrecordingsoutputtest.wav Сайн байна уу
```

### Phase 4 — Speaker support

Read the TTS model's actual speaker mapping instead of assuming IDs.

Implement

```powershell
python -m src.main voices
```

Display available speaker identifiers.

Allow

```powershell
python -m src.main speak --speaker speaker Монгол хэлээр ярьж байна.
```

Store the preferred voice in `config.yaml`.

### Phase 5 — Audio system

Implement microphone recording.

Target

```text
16 kHz
mono
PCM
```

Functions should expose an API similar to

```python
recorder.start()
recorder.stop()
audio = recorder.get_audio()
```

Do not save microphone recordings to disk unless debug recording is explicitly enabled.

### Phase 6 — Push-to-talk

Implement push-to-talk before always-listening mode.

Desired state machine

```text
IDLE
↓
LISTENING
↓
TRANSCRIBING
↓
THINKING
↓
SPEAKING
↓
IDLE
```

Use a configurable Windows hotkey.

Do not hard-code the hotkey deep inside implementation code.

Store it in configuration.

### Phase 7 — Echo test

Before connecting an LLM, make this work

```text
User speaks Mongolian
       ↓
STT
       ↓
recognized Mongolian text
       ↓
same text passed to TTS
       ↓
assistant repeats it
```

This is the first full end-to-end acceptance test.

Implement

```powershell
python -m src.main echo
```

### Phase 8 — Agent abstraction

Implement

```python
from abc import ABC, abstractmethod

class AgentBridge(ABC)

    @abstractmethod
    def ask(self, text str) - str
        ...
```

Initial implementation

```python
class EchoAgent(AgentBridge)

    def ask(self, text str) - str
        return text
```

The speech pipeline must depend only on `AgentBridge`, not directly on any LLM SDK.

Design it so adapters can later be added for

```text
Hermes
Pi agent
local OpenAI-compatible API
Ollama
llama.cpp
OpenAI API
other agents
```

Do not install all those integrations now.

Create a clean adapter boundary only.

### Phase 9 — Voice activity detection

Add VAD after push-to-talk works.

Requirements

```yaml
vad
  enabled true
  silence_timeout_ms 700
  min_speech_ms 250
  max_speech_seconds 30
```

Use a lightweight local VAD implementation appropriate for Windows.

Do not send long silence sections to Whisper.

### Phase 10 — Prevent feedback loops

The assistant must not transcribe its own TTS.

At minimum

```text
TTS starts
↓
microphoneSTT listening pauses

TTS finishes
↓
microphoneSTT resumes
```

Implement explicit audio-system states.

Do not rely only on volume thresholds.

### Phase 11 — Text normalization

Implement a Mongolian TTS preprocessing layer.

Keep

```python
response_text
tts_text
```

separate.

Support normalization hooks for

```text
numbers
dates
times
URLs
abbreviations
English terms
punctuation
```

Do not aggressively rewrite normal Mongolian text.

Implement only transformations that can be tested.

### Phase 12 — Configuration

Use

```text
DAIvoice-assistantconfigconfig.yaml
```

Initial structure

```yaml
system
  language mn

storage
  root DAI
  model_root DAImodels
  recordings DAIrecordings

stt
  model Blgn94whisper-small-mn-v3
  local_path DAImodelssttwhisper-small-mn-v3
  device cuda
  fallback_device cpu

tts
  model Bokhbatmongolian-vits-tts
  local_path DAImodelsttsmongolian-vits-tts
  device cpu
  speaker_id null

audio
  sample_rate 16000
  channels 1

vad
  enabled true
  silence_timeout_ms 700
  min_speech_ms 250
  max_speech_seconds 30

agent
  provider echo

logging
  enabled true
  save_recordings false
```

Validate configuration during startup.

### Phase 13 — Model lifecycle

Models must load once when the service starts.

Do not reload the models for every request.

Implement

```python
voice_system.start()
voice_system.listen()
voice_system.stop()
```

Lifecycle

```text
startup
↓
load STT
↓
load TTS
↓
READY

multiple requests

shutdown
↓
release modelsresources
```

### Phase 14 — Local API

Implement a lightweight local FastAPI service.

Required endpoints

```text
GET  health
GET  voices
POST stt
POST tts
POST chat
```

Bind to

```text
127.0.0.1
```

by default.

Do not expose it to the local network or Internet unless explicitly configured later.

`health` should report

```json
{
  stt_loaded true,
  tts_loaded true,
  stt_device cuda,
  tts_device cpu
}
```

### Phase 15 — Performance metrics

Measure actual performance on this laptop.

Record

```text
STT inference latency
TTS inference latency
total voice-loop latency
GPU VRAM usage
system RAM usage
CPU usage where practical
```

Do not invent expected numbers.

Create a benchmark command

```powershell
python -m src.main benchmark
```

Output an easy-to-read summary.

### Phase 16 — Windows startup scripts

Create

```text
DAIvoice-assistantstart.ps1
```

It should

1. activate the correct virtual environment
2. set required local environment variables if needed
3. validate model paths
4. start the voice system or API
5. fail with readable errors

Do not require navigating manually through multiple directories.

## CLI requirements

At minimum support

```powershell
python -m src.main status
python -m src.main transcribe test.wav
python -m src.main speak Сайн байна уу
python -m src.main voices
python -m src.main echo
python -m src.main listen
python -m src.main benchmark
python -m src.main api
```

`status` should display

```text
STT model
installation status
load status
device

TTS model
installation status
load status
device

CUDA availability
GPU name
VRAM

microphone device
speaker device
```

## Resource strategy

The laptop only has 4 GB VRAM.

Default allocation

```text
RTX 3050
└── Mongolian Whisper STT

Ryzen CPU
└── Mongolian VITS TTS

System RAM
├── Python runtime
├── model CPU memory
└── audio buffers
```

Do not attempt to load everything onto CUDA automatically.

Monitor actual VRAM use.

If STT causes CUDA out-of-memory

1. clear unused CUDA memory
2. inspect dtype
3. use appropriate reduced precision
4. investigate CTranslate2faster-whisper conversion
5. fall back to CPU if necessary

Never silently crash.

## Dependency discipline

Do not blindly pin outdated packages from old tutorials.

Use currently compatible packages.

Before changing versions because of incompatibility

1. identify the actual failing dependency
2. document the reason
3. choose the smallest compatible fix
4. rerun the relevant test

Record final working versions in

```text
requirements.txt
```

or an equivalent lock file.

## Error handling

Components must fail independently.

Examples

```text
STT failure
→ readable transcription error

TTS failure
→ show response as text

CUDA failure
→ CPU fallback

microphone failure
→ list available audio devices

agent failure
→ return readable error instead of crashing voice service
```

## Logging

Logs

```text
DAIvoice-assistantlogs
```

Record

```text
timestamp
system startup
model loading
device selection
STT latency
recognized text
agent latency
TTS latency
errors
```

Do not save raw microphone audio by default.

## Tests

Create actual automated or repeatable tests.

### STT

Test

```text
short Mongolian sentence
long Mongolian sentence
quiet recording
background noise
male voice
female voice
EnglishMongolian mixed sentence
```

Use available test audio where possible.

Do not fabricate accuracy results.

### TTS

Test

```text
normal Mongolian
questions
numbers
dates
English names
long responses
multiple available voices
```

### Full pipeline

Verify

```text
microphone
→ STT
→ text
→ EchoAgent
→ TTS
→ speakers
```

Then verify the AgentBridge path independently.

## Security and autonomy boundaries

This project is a local speech interface.

Do not give the voice interface unrestricted authority over the computer.

The future agent connected behind `AgentBridge` may have its own permissions, but this speech service itself should

 accept speech
 produce text
 forward text
 receive response text
 synthesize speech

Do not add destructive file operations, shell execution from recognized speech, external account actions, messaging, purchases, or system configuration actions as part of this task.

Those should require separate agent-level permission handling.

## Git workflow

If this project is already in a Git repository

1. inspect current status
2. preserve unrelated modifications
3. do not destroy uncommitted work
4. make logically grouped changes

If no repository exists, initialize Git inside

```text
DAIvoice-assistant
```

Use `.gitignore` for

```text
.venv
models
cache
recordings
logs
__pycache__
temporary WAV files
Hugging Face cache
```

Do not commit model weights.

## Verification gates

Do not consider a phase finished simply because code was written.

Required gates

### Gate 1

```text
test WAV
→ Mongolian STT
→ readable text
```

### Gate 2

```text
Mongolian text
→ TTS
→ audible output
```

### Gate 3

```text
microphone
→ STT
```

### Gate 4

```text
microphone
→ STT
→ EchoAgent
→ TTS
→ speaker
```

### Gate 5

```text
push-to-talk
→ full conversation cycle
```

### Gate 6

```text
local API
→ STTTTS health endpoints work
```

### Gate 7

```text
restart machinesession
→ start.ps1
→ system becomes operational without manual repair
```

## Final acceptance criteria

Do not mark the project complete until the following works

I speak

```text
Маргааш хийх ажлуудыг надад хэл.
```

The system

```text
microphone
↓
Mongolian STT
↓
Маргааш хийх ажлуудыг надад хэл.
↓
AgentBridge
↓
Mongolian response
↓
Mongolian TTS
↓
spoken response
```

All speech processing must work locally.

All large AI files must remain under

```text
DAI
```

The system must survive a normal restart without redownloading models.

## Execution behavior

Work autonomously through the implementation.

Do not stop after producing a plan.

For each stage

1. inspect current state
2. implement the smallest working piece
3. run it
4. inspect errors
5. fix them
6. verify success
7. continue

Do not repeatedly ask me to run commands that you can run yourself.

Do not rewrite working components merely for style.

Prefer reliable working software over unnecessary architecture.

If an exact librarymodel API differs from this specification, inspect the actual installed packagemodel files and adapt the implementation rather than forcing obsolete example code.

If something cannot be completed, leave the rest of the system functional and clearly document

 what failed
 the exact error
 what was attempted
 current project state
 the next technically valid step

At completion, provide a concise report containing

```text
Completed components
Models installed and their exact locations
Working dependency versions
STT device
TTS device
Available CLI commands
API address
Measured STTTTS latency
Measured RAMVRAM usage
Known limitations
Files createdmodified
Exact command to start the system
```
