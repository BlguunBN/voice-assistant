from __future__ import annotations

from contextlib import asynccontextmanager
from io import BytesIO
import logging
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.agent import AgentBridge, EchoAgentBridge
from src.core.config import AppConfig, load_config
from src.stt import STTError, STTEngine
from src.tts import TTSError, TTSEngine


LOGGER = logging.getLogger(__name__)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)
    speaker_id: str | None = Field(default=None, max_length=128)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)


class STTResponse(BaseModel):
    transcript: str


class ChatResponse(BaseModel):
    message: str
    response: str


def _loaded(engine: Any) -> bool:
    return bool(getattr(engine, "loaded", False))


def _error(operation: str, exc: Exception) -> HTTPException:
    LOGGER.exception("API %s failed", operation)
    return HTTPException(status_code=500, detail=f"{operation} failed: {exc}")


def create_app(
    config: AppConfig | None = None,
    *,
    stt: Any | None = None,
    tts: Any | None = None,
    agent: AgentBridge | None = None,
) -> FastAPI:
    """Build the local API with one resident engine instance per process."""
    app_config = config or load_config()
    stt_engine = stt or STTEngine(app_config)
    tts_engine = tts or TTSEngine(app_config)
    agent_bridge = agent or EchoAgentBridge()
    stt_lock = RLock()
    tts_lock = RLock()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            with stt_lock:
                stt_engine.load()
            with tts_lock:
                tts_engine.load()
            yield
        finally:
            with stt_lock:
                stt_engine.unload()
            with tts_lock:
                tts_engine.unload()

    app = FastAPI(
        title="Local Mongolian Voice Assistant API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "local-mongolian-voice-assistant",
            "agent_bridge": type(agent_bridge).__name__,
            "stt_loaded": _loaded(stt_engine),
            "tts_loaded": _loaded(tts_engine),
            "bind_host": app_config.api_host,
            "external_network_exposure": False,
        }

    @app.get("/voices")
    def voices() -> dict[str, object]:
        try:
            with tts_lock:
                values = list(tts_engine.voices())
            return {"voices": values, "count": len(values)}
        except (TTSError, OSError, ValueError) as exc:
            raise _error("voice discovery", exc) from exc

    @app.post("/stt", response_model=STTResponse)
    async def transcribe(file: UploadFile = File(...)) -> STTResponse:
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
                transcript = stt_engine.transcribe(temporary_path)
            transcript = transcript.strip()
            if not transcript:
                raise HTTPException(status_code=422, detail="STT returned an empty transcript")
            return STTResponse(transcript=transcript)
        except HTTPException:
            raise
        except (STTError, OSError, ValueError) as exc:
            raise _error("transcription", exc) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @app.post("/tts")
    def synthesize(request: TTSRequest) -> Response:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=".wav",
                dir=app_config.project_root / "cache",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
            with tts_lock:
                output_path = Path(tts_engine.synthesize(request.text, request.speaker_id, temporary_path))
            audio = output_path.read_bytes()
            return Response(
                content=audio,
                media_type="audio/wav",
                headers={"X-Voice-Assistant-Speaker": request.speaker_id or "default"},
            )
        except (TTSError, OSError, ValueError) as exc:
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
        except (OSError, RuntimeError, ValueError) as exc:
            raise _error("agent response", exc) from exc
        if not response:
            raise HTTPException(status_code=502, detail="Agent bridge returned an empty response")
        return ChatResponse(message=message, response=response)

    return app


def serve(config: AppConfig | None = None) -> None:
    """Run the API on the validated loopback address."""
    import uvicorn

    app_config = config or load_config()
    uvicorn.run(create_app(app_config), host=app_config.api_host, port=app_config.api_port, log_level="info")


app = create_app()
