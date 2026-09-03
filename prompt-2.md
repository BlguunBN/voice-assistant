## Staged execution checkpoints

Do not attempt the entire project in one uninterrupted implementation run.

Execute the project in the stages below. At the end of every stage, complete its verification checkpoint, produce a status report, and STOP. Do not begin the next stage until I explicitly send:

```text
CONTINUE
```

If a stage fails, remain within that stage. Diagnose and repair the failure before presenting the checkpoint.

Do not bypass a failed verification gate merely to make progress.

### Stage 0 — Preflight inspection

Perform inspection only.

Inspect:

```text
Windows version
D: drive availability and free space
Python installations
Git
PowerShell
NVIDIA driver
nvidia-smi
CUDA visibility
existing PyTorch installations
existing D:\AI contents
existing voice-assistant project
existing Hugging Face environment variables
microphone/audio devices where detectable
Git repository/status if present
```

Do not download models or make major dependency changes during this stage.

Determine:

```text
Python version to use
PyTorch/CUDA build to use
project paths
model paths
current Git state
potential compatibility problems
```

Checkpoint report:

```text
STAGE 0 — PREFLIGHT

Status: PASS / FAIL

Windows:
Python:
Git:
GPU:
NVIDIA driver:
CUDA reported by driver:
RAM:
D: free space:

Existing project:
Existing Git state:
HF_HOME:
HF_HUB_CACHE:

Planned Python version:
Planned PyTorch build:

Detected blockers:
Files changed:
Commands executed:

Next stage:
Environment + project bootstrap
```

STOP after this report.

---

### Stage 1 — Environment + STT

Implement only:

```text
project directory
virtual environment
Hugging Face cache relocation
dependencies required for STT
CUDA-enabled PyTorch
STT model download
STTEngine
file-based transcription CLI
basic configuration
STT tests
```

Required verification:

```text
python -m src.main status
python -m src.main transcribe "<verified Mongolian WAV>"
```

Verify:

```text
PyTorch imports successfully
torch.cuda.is_available() result is recorded
RTX 3050 is detected when CUDA is used
model resides on D:
Hugging Face cache resides on D:
STT model loads
WAV transcription executes successfully
recognized text is actually returned
C: was not used for large model storage
```

Measure:

```text
STT model disk usage
STT load time
STT inference latency
GPU VRAM use during transcription
system RAM use where practical
```

Checkpoint report:

```text
STAGE 1 — STT

Status: PASS / FAIL

Project:
Virtual environment:
Python:
PyTorch:
CUDA:
STT model:
STT model path:
Model disk size:

Test WAV:
Recognized text:

STT load time:
STT inference latency:
Peak/observed VRAM:
Observed RAM:

Files created/modified:
Dependencies installed:
Git status:
Known problems:

Verification commands:
<commands and results>

Next stage:
Mongolian TTS
```

Commit working source changes if Git is being used, but never commit model weights, caches, recordings, `.venv`, or secrets.

STOP after this report.

---

### Stage 2 — TTS

Implement only:

```text
TTS dependencies
Bokhbat/mongolian-vits-tts download
TTSEngine
CPU inference
WAV generation
Windows playback
speaker discovery
speaker selection
TTS tests
```

Do not implement microphone functionality yet.

Required verification:

```powershell
python -m src.main voices
python -m src.main speak "Сайн байна уу"
python -m src.main speak --output "D:\AI\recordings\output\checkpoint.wav" "Монгол хэлээр ярьж байна."
```

Verify:

```text
TTS model is stored on D:
model loads successfully
Mongolian audio is generated
output WAV is valid
Windows playback succeeds where available
speaker mapping is read from the actual model
selected speaker can be changed
TTS remains on CPU unless there is a verified reason to change it
```

Measure:

```text
TTS model disk usage
TTS load time
TTS synthesis latency
audio duration
real-time factor if calculable
system RAM use
```

Real-time factor calculation:

```text
RTF = synthesis_time_seconds / generated_audio_duration_seconds
```

Checkpoint report:

```text
STAGE 2 — TTS

Status: PASS / FAIL

TTS model:
TTS path:
Model disk size:
Device:
Available speakers:

Test text:
Output WAV:

TTS load time:
Synthesis time:
Generated audio duration:
RTF:
Observed RAM:

Files created/modified:
Dependencies installed:
Git status:
Known problems:

Verification commands:
<commands and results>

Next stage:
Microphone + push-to-talk + echo pipeline
```

STOP after this report.

---

### Stage 3 — Audio + push-to-talk + echo

Implement:

```text
microphone device discovery
audio capture
speaker playback abstraction
push-to-talk
state machine
STT microphone transcription
EchoAgent
full STT → TTS echo loop
```

Do not implement always-listening mode yet.

Required state machine:

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

Required verification:

```text
microphone records real speech
recording is passed to STT
Mongolian transcript appears
EchoAgent returns the transcript
TTS speaks the result
system returns to IDLE
```

Run:

```powershell
python -m src.main status
python -m src.main echo
python -m src.main listen
```

Checkpoint report:

```text
STAGE 3 — END-TO-END ECHO

Status: PASS / FAIL

Input device:
Output device:
Sample rate:
Push-to-talk hotkey:

Spoken test:
Recognized text:
Echo response:
TTS result:

STT latency:
TTS latency:
Total end-of-speech → audio-start latency:

State transitions verified:
Feedback/self-transcription observed:

Files created/modified:
Git status:
Known problems:

Next stage:
VAD + feedback prevention + production pipeline
```

STOP after this report.

---

### Stage 4 — VAD + feedback protection + runtime architecture

Implement:

```text
voice activity detection
silence termination
minimum speech handling
maximum utterance duration
TTS/microphone mutual exclusion
feedback-loop prevention
configuration validation
model lifecycle
persistent model loading
clean shutdown
text normalization framework
```

Required verification:

```text
silence does not trigger unnecessary STT
normal speech starts capture
configured silence ends capture
TTS pauses listening
assistant speech is not fed back into STT
models remain loaded across multiple requests
shutdown releases resources cleanly
```

Test at least three consecutive voice turns without reloading models.

Checkpoint report:

```text
STAGE 4 — RUNTIME PIPELINE

Status: PASS / FAIL

VAD implementation:
VAD thresholds:

Three-turn test:
Turn 1:
Turn 2:
Turn 3:

STT reloads detected:
TTS reloads detected:
Self-transcription detected:

Average STT latency:
Average TTS latency:
Average total latency:
Observed VRAM:
Observed RAM:

Files created/modified:
Git status:
Known problems:

Next stage:
Agent API + local service
```

STOP after this report.

---

### Stage 5 — Agent bridge + REST API

Implement:

```text
AgentBridge abstraction
EchoAgent
clean adapter interface for future agents
FastAPI server
GET /health
GET /voices
POST /stt
POST /tts
POST /chat
localhost-only binding
API error handling
```

Do not add shell execution, arbitrary computer control, external messaging, purchases, or unrelated agent permissions.

Bind by default to:

```text
127.0.0.1
```

Required verification:

```text
GET /health
GET /voices
POST /tts
POST /stt
POST /chat
```

Verify that `/chat` passes through `AgentBridge` rather than directly depending on a specific LLM SDK.

Checkpoint report:

```text
STAGE 5 — LOCAL API

Status: PASS / FAIL

API address:
Binding:
Agent provider:

/health:
/voices:
/stt:
/tts:
/chat:

Security boundary:
External network exposure:

Files created/modified:
Git status:
Known problems:

Next stage:
Optimization + benchmark + startup/restart validation
```

STOP after this report.

---

### Stage 6 — Optimization + final acceptance

Only after all previous stages pass, perform optimization.

Evaluate:

```text
Transformers STT performance
GPU memory consumption
float16 suitability
CTranslate2/faster-whisper conversion feasibility
CPU fallback
startup performance
dependency cleanup
logging
benchmark command
Windows startup script
restart persistence
```

Do not replace the working Transformers STT implementation until the alternative has been independently verified.

If testing CTranslate2/faster-whisper:

```text
1. preserve the working Transformers implementation
2. convert to a separate model directory
3. compare transcription output
4. compare latency
5. compare RAM
6. compare VRAM
7. keep the faster implementation only if it remains reliable
```

Run:

```powershell
python -m src.main status
python -m src.main benchmark
python -m src.main voices
python -m src.main echo
python -m src.main api
```

Verify `start.ps1`.

Verify that reopening a fresh PowerShell session does not trigger model redownloads.

Where machine restart is not possible from the current execution environment, verify everything that can be verified without rebooting and explicitly mark the restart test as unverified rather than claiming success.

Final checkpoint report:

```text
STAGE 6 — FINAL ACCEPTANCE

Status: PASS / FAIL

Completed components:

STT model:
STT location:
STT device:
STT implementation:

TTS model:
TTS location:
TTS device:
Selected voice:

Total model storage:
Hugging Face cache location:

STT latency:
TTS latency:
End-to-end latency:
VRAM:
RAM:

CLI commands:
API address:

start.ps1:
Fresh-shell test:
Restart test:

Tests passed:
Tests failed:

Known limitations:

Files created/modified:

Exact startup command:
```

---

## Checkpoint rules

These rules apply to every stage.

1. Do not begin another stage before the current stage passes its required verification or the failure is explicitly documented.
2. Do not interpret successful installation as successful functionality.
3. Execute the actual verification commands.
4. Record real command results rather than expected results.
5. Never fabricate benchmark results, transcription quality, RAM usage, VRAM usage, or successful audio playback.
6. If audio playback or microphone verification requires hardware interaction unavailable to the execution environment, mark that specific test `UNVERIFIED`.
7. Preserve every previously working stage while implementing later stages.
8. Before significant dependency changes, ensure the current working state can be recovered through Git or documented package versions.
9. Never delete a working model or environment merely to retry an installation without first identifying the failure.
10. Keep model weights, caches, `.venv`, recordings, and generated WAV files out of Git.
11. At every checkpoint run `git status` when the project is under Git.
12. Include unexpected changes in the checkpoint report.
13. A checkpoint status may only be:

```text
PASS
FAIL
PARTIAL — external/manual verification required
```

14. After producing the checkpoint report, stop execution completely.
15. Resume only when my next instruction is exactly or clearly equivalent to:

```text
CONTINUE
```

When resuming, inspect the previous stage's actual filesystem and Git state instead of assuming the checkpoint report is still accurate.
