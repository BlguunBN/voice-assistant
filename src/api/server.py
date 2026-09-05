from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.agent import AgentBridge, EchoAgentBridge, NIMError, NvidiaNIMAgentBridge
from src.core.config import AppConfig, load_config
from src.desktop.preferences import DesktopPreferencesStore
from src.desktop.status import DesktopStatusStore
from src.stt import STTError, STTLanguageRouter
from src.stt.router import STTLanguage
from src.tts import EdgeMongolianTTSEngine, EdgeTTSError, EnglishTTSEngine, TTSError, TTSEngine

LOGGER = logging.getLogger(__name__)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)
    speaker_id: str | None = Field(default=None, max_length=128)
    language: Literal["mn", "en"] = "mn"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)
    language: Literal["mn", "en"] = "mn"


class STTResponse(BaseModel):
    transcript: str
    detected_language: Literal["mn", "en"] | None = None


class DesktopPreferencesRequest(BaseModel):
    selected_language: Literal["mn", "en", "auto"]

class ChatResponse(BaseModel):
    message: str
    response: str


def _loaded(engine: Any) -> bool:
    return bool(getattr(engine, "loaded", False))


def _error(operation: str, exc: Exception, status_code: int = 500) -> HTTPException:
    LOGGER.exception("API %s failed", operation)
    return HTTPException(status_code=status_code, detail=f"{operation} failed: {exc}")


def _transcribe(engine: Any, audio_path: Path, language: STTLanguage) -> str:
    if isinstance(engine, STTLanguageRouter):
        return engine.transcribe(audio_path, language=language)
    # Keep the legacy fake-engine contract while routing non-default languages.
    if language == "mn":
        return engine.transcribe(audio_path)
    return engine.transcribe(audio_path, language=language if language != "auto" else None)


def create_app(
    config: AppConfig | None = None,
    *,
    stt: Any | None = None,
    tts: Any | None = None,
    agent: AgentBridge | None = None,
    english_tts: Any | None = None,
) -> FastAPI:
    """Build the local bilingual API with one resident engine instance per process."""
    app_config = config or load_config()
    stt_engine = stt or STTLanguageRouter(app_config)
    tts_engine = tts or (
        EdgeMongolianTTSEngine(app_config)
        if app_config.tts_provider == "edge"
        else TTSEngine(app_config)
    )
    english_tts_engine = english_tts or EnglishTTSEngine(app_config)
    if agent is not None:
        agent_bridge = agent
    elif app_config.llm_provider == "nvidia_nim":
        agent_bridge = NvidiaNIMAgentBridge(app_config)
    else:
        agent_bridge = EchoAgentBridge()
    stt_lock = RLock()
    tts_lock = RLock()
    english_tts_lock = RLock()
    cache_dir = app_config.project_root / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    desktop_status_store = DesktopStatusStore(cache_dir / "desktop-status.json")
    desktop_preferences_store = DesktopPreferencesStore(cache_dir / "desktop-preferences.json")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            with stt_lock:
                stt_engine.load()
            with tts_lock:
                tts_engine.load()
            with english_tts_lock:
                english_tts_engine.load()
            yield
        finally:
            with stt_lock:
                stt_engine.unload()
            with tts_lock:
                tts_engine.unload()
            with english_tts_lock:
                english_tts_engine.unload()

    app = FastAPI(
        title="Bilingual Local Voice Assistant API",
        version="0.2.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "local-bilingual-voice-assistant",
            "agent_bridge": type(agent_bridge).__name__,
            "llm_provider": app_config.llm_provider,
            "llm_model": app_config.llm_model or None,
            "llm_configured": bool(getattr(agent_bridge, "configured", app_config.llm_provider == "echo")),
            "stt_loaded": _loaded(stt_engine),
            "tts_loaded": _loaded(tts_engine),
            "english_tts_loaded": _loaded(english_tts_engine),
            "bind_host": app_config.api_host,
            "external_network_exposure": False,
        }

    @app.get("/desktop/status")
    def desktop_status() -> dict[str, object]:
        payload = desktop_status_store.read().as_dict()
        payload["selected_language"] = desktop_preferences_store.read().selected_language
        return payload

    @app.get("/desktop/preferences")
    def desktop_preferences() -> dict[str, object]:
        return desktop_preferences_store.read().as_dict()

    @app.put("/desktop/preferences")
    def update_desktop_preferences(request: DesktopPreferencesRequest) -> dict[str, object]:
        return desktop_preferences_store.update(request.selected_language).as_dict()

    @app.get("/voices")
    def voices() -> dict[str, object]:
        try:
            with tts_lock:
                values = list(tts_engine.voices())
            return {"voices": values, "count": len(values)}
        except (EdgeTTSError, TTSError, OSError, ValueError) as exc:
            raise _error("voice discovery", exc) from exc

    @app.post("/stt", response_model=STTResponse, response_model_exclude_none=True)
    async def transcribe(
        file: UploadFile = File(...),
        language: Literal["mn", "en", "auto"] = Form("mn"),
    ) -> STTResponse:
        content = await file.read(app_config.api_max_upload_bytes + 1)
        if len(content) > app_config.api_max_upload_bytes:
            raise HTTPException(status_code=413, detail="Uploaded audio exceeds the configured size limit")
        if not content:
            raise HTTPException(status_code=422, detail="Uploaded audio is empty")

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=".wav",
                dir=app_config.project_root / "cache",
                delete=False,
            ) as temporary_file:
                temporary_file.write(content)
                temporary_path = Path(temporary_file.name)
            with stt_lock:
                transcript = _transcribe(stt_engine, temporary_path, language)
            transcript = transcript.strip()
            if not transcript:
                raise HTTPException(status_code=422, detail="STT returned an empty transcript")
            detected_language = getattr(stt_engine, "detected_language", None) if language == "auto" else None
            return STTResponse(transcript=transcript, detected_language=detected_language)
        except HTTPException:
            raise
        except (STTError, OSError, ValueError, TypeError) as exc:
            raise _error("transcription", exc) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @app.post("/tts")
    def synthesize(request: TTSRequest) -> Response:
        temporary_path: Path | None = None
        selected_tts = tts_engine if request.language == "mn" else english_tts_engine
        selected_lock = tts_lock if request.language == "mn" else english_tts_lock
        try:
            output_suffix = (
                ".mp3"
                if isinstance(selected_tts, EdgeMongolianTTSEngine)
                else ".wav"
            )
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=output_suffix,
                dir=app_config.project_root / "cache",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
            with selected_lock:
                output_path = Path(selected_tts.synthesize(request.text, request.speaker_id, temporary_path))
            audio = output_path.read_bytes()
            return Response(
                content=audio,
                media_type="audio/mpeg" if output_path.suffix.lower() == ".mp3" else "audio/wav",
                headers={
                    "X-Voice-Assistant-Language": request.language,
                    "X-Voice-Assistant-Speaker": request.speaker_id or "default",
                },
            )
        except (EdgeTTSError, TTSError, OSError, ValueError, TypeError) as exc:
            raise _error("speech synthesis", exc) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        message = " ".join(request.message.split())
        if not message:
            raise HTTPException(status_code=422, detail="Message is empty after normalization")
        try:
            response = agent_bridge.respond(message).strip()
        except NIMError as exc:
            raise _error("agent response", exc, status_code=503) from exc
        except (OSError, RuntimeError, ValueError) as exc:
            raise _error("agent response", exc) from exc
        if not response:
            raise HTTPException(status_code=502, detail="Agent bridge returned an empty response")
        return ChatResponse(message=message, response=response)

    return app


def serve(config: AppConfig | None = None) -> None:
    """Run the API on the validated loopback address."""
    app_config = config or load_config()
    import uvicorn

    uvicorn.run(create_app(app_config), host=app_config.api_host, port=app_config.api_port, log_level="info")


app = create_app()
