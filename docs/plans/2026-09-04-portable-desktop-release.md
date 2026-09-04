# Portable Desktop Release Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make the bilingual voice assistant portable, documented, continuously tested, easy to launch on Windows, and controllable by language mode from the desktop UI.

**Architecture:** Keep FastAPI, the STT router, the native desktop companion, and the React control panel as separate existing components. Add one small JSON preference store under the configured cache directory and expose it through local API endpoints so the browser UI and global hotkey companion share the same `auto|en|mn` selection and detected-language status.

**Tech Stack:** Python 3.12, FastAPI, pytest, PyYAML, Tk/pystray, React 19, TypeScript, Vite, Vitest, GitHub Actions, Windows CMD and PowerShell.

---

## Task 1: Add portable path resolution tests

**Objective:** Define the required relative-path and environment-override behavior before changing configuration code.

**Files:**
- Modify: `tests/test_stage1.py`
- Test: temporary YAML configs created inside tests

**Steps:**
1. Add tests proving `storage.project_root: .`, `model_root: models`, `recordings: recordings`, `huggingface_home: huggingface`, and `huggingface_cache: huggingface/hub` resolve relative to the repository/config base.
2. Add a test proving `VOICE_ASSISTANT_ROOT` relocates model/runtime directories without changing YAML.
3. Add a test proving an explicit absolute path remains absolute.
4. Run `./.venv/Scripts/python.exe -m pytest tests/test_stage1.py -q`; expect the new tests to fail before implementation.
5. Commit: `test: define portable configuration paths`.

## Task 2: Implement portable configuration defaults

**Objective:** Remove the default dependency on `D:/AI` while preserving current explicit path support.

**Files:**
- Modify: `src/core/config.py`
- Modify: `config/config.yaml`
- Modify: `.env.example`
- Test: `tests/test_stage1.py`

**Steps:**
1. Add a single `VOICE_ASSISTANT_ROOT` base override read after `.env` loading.
2. Resolve relative storage values from that base, defaulting the base to the repository root.
3. Make all model, recording, cache, log, and Hugging Face properties use the same resolver.
4. Replace `D:/AI` values in `config/config.yaml` with relative paths.
5. Document `VOICE_ASSISTANT_ROOT=` in `.env.example` without adding a real credential.
6. Preserve validation and runtime-directory creation.
7. Run `./.venv/Scripts/python.exe -m pytest tests/test_stage1.py -q`; expect all path tests to pass.
8. Run `./.venv/Scripts/python.exe -m py_compile src/core/config.py`; expect exit 0.
9. Commit: `fix: make runtime paths portable`.

## Task 3: Add shared desktop preference storage

**Objective:** Persist and validate the selected desktop speech mode safely.

**Files:**
- Create: `src/desktop/preferences.py`
- Modify: `src/desktop/__init__.py` if public exports are used
- Test: `tests/test_desktop_preferences.py`

**Steps:**
1. Write tests for default `auto`, valid `auto|en|mn`, rejection of invalid values, atomic persistence, and malformed/missing-file fallback.
2. Run `./.venv/Scripts/python.exe -m pytest tests/test_desktop_preferences.py -q`; expect failure because the store does not exist.
3. Implement a typed preference value and a store rooted at `config.cache_root`.
4. Write updates through a temporary file followed by replacement; never partially overwrite the live preference file.
5. Run the focused test again; expect all tests to pass.
6. Commit: `feat: add shared desktop language preferences`.

## Task 4: Extend desktop status with language information

**Objective:** Expose selected and detected language in the existing status channel.

**Files:**
- Modify: `src/desktop/status.py`
- Modify: `src/desktop/dictation.py`
- Modify: `src/stt/router.py`
- Test: `tests/test_desktop_status.py`
- Test: `tests/test_stt_router.py`

**Steps:**
1. Add tests for status JSON round-trip with `language` and `detected_language`, backward-compatible reads, and offline-safe defaults.
2. Add router coverage proving auto detection updates detected language.
3. Run the focused tests; expect new assertions to fail.
4. Extend the status dataclass and atomic store update without changing existing status fields.
5. Update the desktop processing path to publish selected mode before transcription and detected mode after successful routing.
6. Run `./.venv/Scripts/python.exe -m pytest tests/test_desktop_status.py tests/test_stt_router.py -q`; expect pass.
7. Commit: `feat: expose desktop language status`.

## Task 5: Add local language-preference API endpoints

**Objective:** Give the React control panel a validated local API for shared desktop language mode.

**Files:**
- Modify: `src/api/server.py`
- Test: `tests/test_bilingual_api.py`
- Test: `tests/test_api.py`

**Steps:**
1. Add tests for reading preferences, accepting `auto|en|mn`, rejecting invalid values with `422`, and returning additive status fields.
2. Run the focused API tests; expect failure before endpoint implementation.
3. Add strict Pydantic request/response models and local `GET`/`PUT` preference endpoints.
4. Inject the preference store into `create_app` so tests can use temporary files.
5. Keep `/stt`, `/tts`, `/chat`, `/health`, and `/voices` contracts unchanged.
6. Run `./.venv/Scripts/python.exe -m pytest tests/test_api.py tests/test_bilingual_api.py -q`; expect pass.
7. Commit: `feat: add desktop language preference API`.

## Task 6: Make global desktop dictation consume preferences

**Objective:** Ensure the global `Win + Alt` path uses the mode selected in the control panel.

**Files:**
- Modify: `src/desktop/dictation.py`
- Modify: `src/desktop/overlay.py`
- Test: `tests/test_desktop.py`
- Test: `tests/test_overlay_host.py`

**Steps:**
1. Add a test proving the desktop companion reads the current preference immediately before sending multipart STT data.
2. Add a test proving the selected and detected language are rendered into native overlay state text.
3. Run the focused tests; expect failure before integration.
4. Inject the preference store into `DesktopDictation`, read the mode per recording, and update status transitions.
5. Pass selected/detected values into the native overlay renderer without changing hotkey behavior.
6. Run `./.venv/Scripts/python.exe -m pytest tests/test_desktop.py tests/test_overlay_host.py -q`; expect pass.
7. Commit: `feat: connect desktop dictation to language preferences`.

## Task 7: Add React selector and detected-language status

**Objective:** Implement the approved status-plus-selector desktop UI treatment.

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/OverlayApp.tsx`
- Modify: `frontend/src/hooks/useDesktopStatus.ts`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/audio/wav.test.ts` or a new focused UI test file following current Vitest setup

**Steps:**
1. Add UI tests for rendering `AUTO`, `ENGLISH`, and `MONGOLIAN`, selecting a mode, showing the latest detected language, and showing API/offline errors.
2. Run `cd frontend && npm test -- --run`; expect new assertions to fail.
3. Extend API types/client functions for preference reads/writes and status language fields.
4. Add a controlled three-way selector near the existing status cards; persist the selection through the API and retain local UI state for fast rendering.
5. Render detected language only when useful in automatic mode and keep semantic labels/keyboard operation.
6. Update the native overlay React surface with the same status language treatment and responsive styling.
7. Run `cd frontend && npm test -- --run && npm run build`; expect pass.
8. Commit: `feat: add desktop language selector`.

## Task 8: Add one-click Windows startup launcher

**Objective:** Start API, frontend, and desktop companion from any checkout location.

**Files:**
- Create: `scripts/start_all.cmd`
- Test: `tests/test_startup_scripts.py` or shell-independent text/behavior tests
- Modify: `.gitignore` if launcher logs need exclusion

**Steps:**
1. Add tests/checks for `%~dp0`-based root discovery, virtual-environment validation, frontend dependency validation, and command arguments.
2. Run the focused checks; expect failure before the launcher exists.
3. Implement a CMD launcher that uses `start` for the API, Vite dev server, and desktop companion, with a clear error and `pause` on missing prerequisites.
4. Pass `VOICE_ASSISTANT_ROOT`/config location through the launch environment without embedding a drive letter.
5. Manually run `scripts\start_all.cmd` from a second working directory and verify API health plus desktop process presence.
6. Commit: `feat: add portable Windows startup launcher`.

## Task 9: Add optional current-user auto-start scripts

**Objective:** Provide reversible Windows Startup-folder registration.

**Files:**
- Create: `scripts/install-autostart.ps1`
- Create: `scripts/uninstall-autostart.ps1`
- Test: `tests/test_startup_scripts.py`

**Steps:**
1. Add tests/checks for deterministic shortcut name, current-user Startup path, idempotent install, and uninstall scope.
2. Run the focused checks; expect failure before the scripts exist.
3. Implement install using a `.lnk` shortcut targeting `start_all.cmd`, with working directory set to the repository root.
4. Implement uninstall to remove only the deterministic shortcut.
5. Validate PowerShell syntax with `powershell -NoProfile -Command "& { [scriptblock]::Create((Get-Content scripts/install-autostart.ps1 -Raw)) | Out-Null; [scriptblock]::Create((Get-Content scripts/uninstall-autostart.ps1 -Raw)) | Out-Null }"`.
6. Run install twice, verify one shortcut, run uninstall, and verify it is gone.
7. Commit: `feat: add reversible Windows autostart`.

## Task 10: Add Python and frontend GitHub Actions CI

**Objective:** Run the same meaningful checks on every push and pull request.

**Files:**
- Create: `.github/workflows/ci.yml`
- Possibly create: `requirements-ci.txt` if CPU-only dependency installation is needed

**Steps:**
1. Define Python and frontend jobs with least-privilege `contents: read` permissions.
2. Python job: checkout, setup Python 3.12, cache pip, install project dependencies, run full pytest and compileall.
3. Frontend job: checkout, setup Node, cache npm, run `npm ci`, `npm test -- --run`, and `npm run build`.
4. Keep model downloads disabled and use the existing mocked tests.
5. Validate YAML structure with a parser and run local equivalents before committing.
6. Commit: `ci: add Python and frontend checks`.

## Task 11: Write README and detailed setup guide

**Objective:** Make a fresh Windows clone usable without conversation context.

**Files:**
- Create: `README.md`
- Create: `docs/setup.md`

**Steps:**
1. Document what the assistant does, architecture, supported languages, and privacy boundary.
2. Add a shortest-path setup using the portable launcher.
3. Document Python/Node prerequisites, CUDA/CPU expectations, `.env` creation, NVIDIA API credentials, model directories, and `VOICE_ASSISTANT_ROOT`.
4. Document API, frontend, desktop, hotkey, language selector, model download, logs, troubleshooting, and autostart install/uninstall.
5. Include tested commands for Python tests, frontend tests/build, API health, and launcher startup.
6. Check all commands against the repository's actual scripts and config.
7. Commit: `docs: add setup and usage guides`.

## Task 12: Run full verification and publish

**Objective:** Verify every acceptance criterion and push the completed release.

**Files:**
- Modify only if verification exposes a defect.

**Steps:**
1. Run `./.venv/Scripts/python.exe -m pytest -q`.
2. Run `./.venv/Scripts/python.exe -m compileall -q src tests`.
3. Run `cd frontend && npm test -- --run && npm run build`.
4. Run launcher and API health smoke tests from outside the repository working directory.
5. Run the live English and Mongolian microphone smoke test with `Win + Alt` where the desktop session permits.
6. Validate the GitHub Actions YAML and inspect the final diff for secrets, generated artifacts, and hardcoded `D:/AI` paths.
7. Push `main` to `origin` and verify the remote commit and workflow status with `gh`.
8. Commit any verification-only fixes with focused messages; do not claim CI success until GitHub checks are freshly observed.
