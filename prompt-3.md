## Manual verification checklist

Some requirements cannot be reliably validated by an automated coding agent because they depend on what I physically hear, say, or observe on the Windows laptop.

At the end of each applicable stage, present the corresponding manual checklist and STOP.

Do not mark any item complete on my behalf.

Use these exact states:

```text
[ ] NOT TESTED
[x] PASSED BY USER
[!] FAILED BY USER
[-] NOT APPLICABLE
```

When manual verification is required, the overall stage status must remain:

```text
PARTIAL — external/manual verification required
```

until I provide the result.

After presenting a manual checklist, wait for my response.

Accept responses such as:

```text
1 pass
2 pass
3 fail: microphone used wrong device
```

Update the recorded checkpoint state accordingly.

If any required manual item fails:

1. keep the current stage active
2. diagnose the reported failure
3. make the smallest corrective change
4. rerun automated verification
5. present only the affected manual tests again
6. do not advance to the next stage

---

### Manual checklist — Stage 0

No physical audio verification is required.

I should manually confirm only:

```text
[ ] D:\AI is the intended storage location.
[ ] The reported D: free space looks correct.
[ ] The detected GPU is NVIDIA RTX 3050 Laptop GPU.
[ ] No unexpected existing project files are scheduled for deletion or replacement.
```

Present:

```text
MANUAL CHECK — STAGE 0

1. [ ] D:\AI storage location confirmed
2. [ ] D: free-space report looks correct
3. [ ] RTX 3050 detection confirmed
4. [ ] Existing project preservation confirmed

Reply with the result of each item.
```

---

### Manual checklist — Stage 1 STT

The automated agent may verify that transcription executes, but I must confirm whether the recognition is actually usable Mongolian.

Prepare or use a real Mongolian recording.

I must verify:

```text
[ ] The test audio contains understandable Mongolian speech.
[ ] The generated transcript is Mongolian Cyrillic.
[ ] The transcript roughly matches what was spoken.
[ ] No obvious repeated garbage text appears.
[ ] STT completes without the system becoming unusably slow.
```

Present the exact transcript produced by the system before asking me to verify it.

Manual report format:

```text
MANUAL CHECK — STAGE 1 STT

Audio used:
<file>

Actual transcript:
<exact model output>

1. [ ] Audio contains valid Mongolian speech
2. [ ] Output is Mongolian Cyrillic
3. [ ] Transcript approximately matches speech
4. [ ] No severe hallucination/repetition
5. [ ] Responsiveness is acceptable

Do not alter or clean the model output before showing it.
```

If possible, also show:

```text
Inference time:
Audio duration:
Real-time factor:
```

For STT:

```text
RTF = inference_time_seconds / audio_duration_seconds
```

---

### Manual checklist — Stage 2 TTS

I must listen to the generated audio.

Generate a fixed baseline sentence:

```text
Сайн байна уу. Монгол хэлээр ярьж байна.
```

Also generate:

```text
Өнөөдөр хоёр мянга хорин зургаан оны есдүгээр сарын гурав.
```

I must verify:

```text
[ ] Audio plays through the expected Windows output device.
[ ] Speech is recognizably Mongolian.
[ ] Words are understandable.
[ ] Pronunciation is acceptable.
[ ] Audio is not severely distorted.
[ ] Audio volume is usable.
[ ] Sentence endings are not cut off.
[ ] Changing the speaker changes the voice when multiple speakers are available.
```

Present:

```text
MANUAL CHECK — STAGE 2 TTS

Generated files:
1. <path>
2. <path>

Selected speaker:
<speaker>

1. [ ] Playback works
2. [ ] Speech sounds Mongolian
3. [ ] Words are understandable
4. [ ] Pronunciation is acceptable
5. [ ] No severe distortion
6. [ ] Volume is usable
7. [ ] Endings are not clipped
8. [ ] Speaker selection works

Do not claim TTS quality is good until I confirm it.
```

---

### Manual checklist — Stage 3 microphone

I must verify the real microphone path.

Before testing, show detected input devices and identify the selected device.

I must verify:

```text
[ ] The correct microphone is selected.
[ ] Push-to-talk begins recording.
[ ] Releasing the key stops recording.
[ ] My real voice is captured.
[ ] The recording is not silent.
[ ] The recording does not use the laptop speaker output as the primary input.
[ ] Mongolian speech is transcribed.
```

Present:

```text
MANUAL CHECK — STAGE 3 MICROPHONE

Selected input device:
<device>

Selected output device:
<device>

Push-to-talk key:
<hotkey>

1. [ ] Correct microphone
2. [ ] Hotkey starts capture
3. [ ] Hotkey stops capture
4. [ ] Voice is captured
5. [ ] Recording is not silent
6. [ ] Wrong loopback device is not being used
7. [ ] Mongolian transcription works
```

If the microphone fails, show available input devices before changing configuration.

---

### Manual checklist — Stage 3 echo loop

After microphone verification passes, run the complete echo test:

```text
I speak
↓
STT
↓
EchoAgent
↓
TTS
↓
I hear the same sentence
```

Use at least these three spoken tests:

```text
Test 1:
Сайн байна уу?

Test 2:
Намайг сонсож байна уу?

Test 3:
Монгол хэлээр ярьж байна.
```

I must verify:

```text
[ ] All three utterances trigger the pipeline.
[ ] STT recognizes enough of each sentence to understand it.
[ ] TTS speaks the response.
[ ] The assistant does not freeze between stages.
[ ] The application returns to IDLE after speaking.
```

Present:

```text
MANUAL CHECK — STAGE 3 ECHO

Test 1 transcript:
<text>

Test 2 transcript:
<text>

Test 3 transcript:
<text>

1. [ ] All three speech tests triggered
2. [ ] STT was usable
3. [ ] TTS response was audible
4. [ ] No pipeline freeze
5. [ ] Returned to IDLE
```

---

### Manual checklist — Stage 4 VAD

Test the system without push-to-talk where applicable.

I must verify:

```text
[ ] Silence does not trigger transcription.
[ ] Normal speaking starts capture.
[ ] A natural pause inside a sentence does not cut speech too aggressively.
[ ] Finishing a sentence eventually ends capture.
[ ] Very short accidental noises do not normally trigger a full request.
[ ] Long speech is handled up to the configured maximum.
```

Run these cases:

```text
Test A:
Remain silent for 10 seconds.

Test B:
Speak one normal sentence.

Test C:
Speak a sentence with a brief pause in the middle.

Test D:
Make a short non-speech noise.

Test E:
Speak continuously for several seconds.
```

Present:

```text
MANUAL CHECK — STAGE 4 VAD

1. [ ] 10 s silence caused no request
2. [ ] Normal speech triggered correctly
3. [ ] Brief pause did not cut speech incorrectly
4. [ ] End of speech detected correctly
5. [ ] Short noise did not cause unwanted request
6. [ ] Longer speech remained usable
```

---

### Manual checklist — Stage 4 feedback prevention

This test is mandatory.

Run TTS while the microphone remains physically connected.

I must verify:

```text
[ ] The assistant does not transcribe its own TTS output.
[ ] TTS does not trigger a second response.
[ ] The assistant does not enter a self-conversation loop.
[ ] Microphone listening resumes after TTS finishes.
```

Manual report:

```text
MANUAL CHECK — FEEDBACK

1. [ ] No self-transcription
2. [ ] No second response caused by TTS
3. [ ] No feedback loop
4. [ ] Listening resumed after TTS
```

Any failure here blocks advancement.

---

### Manual checklist — Stage 4 consecutive-turn test

Run at least three consecutive voice interactions without restarting the application.

I must verify:

```text
[ ] Turn 1 works.
[ ] Turn 2 works.
[ ] Turn 3 works.
[ ] STT remains responsive.
[ ] TTS remains responsive.
[ ] Audio devices remain functional.
[ ] No obvious accumulating delay appears.
[ ] No restart is required between turns.
```

Present:

```text
MANUAL CHECK — THREE TURN TEST

Turn 1 transcript:
<text>

Turn 2 transcript:
<text>

Turn 3 transcript:
<text>

1. [ ] Turn 1 passed
2. [ ] Turn 2 passed
3. [ ] Turn 3 passed
4. [ ] STT remained responsive
5. [ ] TTS remained responsive
6. [ ] Audio devices remained active
7. [ ] No severe latency buildup
8. [ ] No restart required
```

---

### Manual checklist — Stage 5 API

Automated HTTP tests should run first.

Afterward, I only need to verify externally visible behavior.

I must verify:

```text
[ ] API binds only to localhost by default.
[ ] /health reports expected model/device state.
[ ] /voices returns real model speakers.
[ ] /tts creates playable Mongolian audio.
[ ] /stt accepts valid audio and returns text.
[ ] /chat uses AgentBridge.
```

Present:

```text
MANUAL CHECK — STAGE 5 API

API:
http://127.0.0.1:<port>

1. [ ] Localhost-only access confirmed
2. [ ] /health output looks correct
3. [ ] /voices output looks correct
4. [ ] /tts output is playable
5. [ ] /stt output is usable
6. [ ] /chat behavior is correct
```

Do not ask me to manually verify properties already fully proven by automated tests unless they affect observable functionality.

---

### Manual checklist — Stage 6 performance

Provide measured values first.

I must evaluate perceived responsiveness separately.

Show:

```text
STT load time
STT inference time
TTS load time
TTS synthesis time
TTS RTF
end-of-speech → assistant-audio-start latency
VRAM usage
RAM usage
```

I must verify:

```text
[ ] Interaction latency feels usable.
[ ] Laptop remains responsive during STT.
[ ] Laptop remains responsive during TTS.
[ ] No severe audio stutter occurs.
[ ] GPU does not repeatedly run out of memory.
[ ] Repeated use does not progressively degrade performance.
```

Present:

```text
MANUAL CHECK — PERFORMANCE

Measured STT latency:
Measured TTS latency:
Measured end-to-end latency:
Measured VRAM:
Measured RAM:

1. [ ] Voice latency feels usable
2. [ ] System remains responsive during STT
3. [ ] System remains responsive during TTS
4. [ ] No severe playback stutter
5. [ ] No recurring CUDA OOM
6. [ ] Repeated requests remain stable
```

---

### Manual checklist — Fresh PowerShell session

Close the current terminal.

Open a new PowerShell window.

Run only the documented startup command.

I must verify:

```text
[ ] No manual environment repair is required.
[ ] Hugging Face models are not downloaded again.
[ ] STT finds its existing model.
[ ] TTS finds its existing model.
[ ] CUDA is detected as expected.
[ ] Voice service becomes operational.
```

Present the expected startup command before stopping:

```powershell
<exact startup command>
```

Checklist:

```text
MANUAL CHECK — FRESH SESSION

1. [ ] Startup command works
2. [ ] No model redownload
3. [ ] STT model found
4. [ ] TTS model found
5. [ ] CUDA state correct
6. [ ] Voice service operational
```

---

### Manual checklist — Restart

This is the final persistence test.

I must:

```text
1. reboot Windows
2. open PowerShell
3. run the documented startup command
4. test one STT request
5. test one TTS request
6. test one microphone → STT → AgentBridge → TTS interaction
```

I must verify:

```text
[ ] Startup works after reboot.
[ ] No models are redownloaded.
[ ] D:\AI paths remain valid.
[ ] Microphone works.
[ ] STT works.
[ ] TTS works.
[ ] Full pipeline works.
```

Present:

```text
MANUAL CHECK — RESTART

Startup command:
<exact command>

1. [ ] Starts after reboot
2. [ ] No model redownload
3. [ ] D:\AI paths valid
4. [ ] Microphone works
5. [ ] STT works
6. [ ] TTS works
7. [ ] Full voice loop works
```

Do not mark the restart acceptance gate as passed until I explicitly report the result.

---

## Final manual acceptance test

The final project cannot receive `PASS` until I complete this test.

I speak naturally into the configured microphone:

```text
Маргааш хийх ажлуудыг надад хэл.
```

The system must perform:

```text
microphone
↓
Mongolian STT
↓
AgentBridge
↓
Mongolian response
↓
Mongolian TTS
↓
speaker
```

I must confirm:

```text
[ ] My speech was detected correctly.
[ ] The STT transcript was understandable.
[ ] AgentBridge received the transcript.
[ ] A response was produced.
[ ] TTS produced understandable Mongolian.
[ ] The audio played successfully.
[ ] The assistant did not hear itself.
[ ] The system returned to listening/idle state correctly.
```

Final report:

```text
FINAL MANUAL ACCEPTANCE

1. [ ] Speech detection
2. [ ] Mongolian STT
3. [ ] AgentBridge
4. [ ] Response generation
5. [ ] Mongolian TTS
6. [ ] Audio playback
7. [ ] No self-feedback
8. [ ] Returned to correct runtime state

Overall:
PASS / FAIL
```

Only after all mandatory automated gates and this final manual acceptance test pass may the project be reported as complete.
