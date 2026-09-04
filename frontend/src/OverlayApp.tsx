import { useEffect, useState } from "react";
import { useDesktopStatus } from "./hooks/useDesktopStatus";
import type { DesktopStatus } from "./types";

type OverlayState = DesktopStatus["status"] | "offline";

type StateCopy = {
  eyebrow: string;
  title: string;
  detail: string;
};

const stateCopy: Record<OverlayState, StateCopy> = {
  armed: {
    eyebrow: "VOICE ASSISTANT",
    title: "Ready when you are",
    detail: "Hold Win + Alt to dictate",
  },
  listening: {
    eyebrow: "CAPTURING AUDIO",
    title: "Listening",
    detail: "Release Win + Alt to transcribe",
  },
  transcribing: {
    eyebrow: "MONGOLIAN STT",
    title: "Transcribing",
    detail: "Whisper is turning your voice into text",
  },
  pasting: {
    eyebrow: "TEXT READY",
    title: "Inserted into your app",
    detail: "Your active window has the transcript",
  },
  error: {
    eyebrow: "DESKTOP COMPANION",
    title: "Needs attention",
    detail: "The last dictation could not be completed",
  },
  offline: {
    eyebrow: "DESKTOP COMPANION",
    title: "Overlay offline",
    detail: "Start the local API and tray companion",
  },
};

const waveformBars = [24, 38, 18, 46, 31, 54, 26, 43, 20, 35, 48, 27, 40, 23, 51, 30, 44, 19];

function isOverlayState(value: string): value is OverlayState {
  return value in stateCopy;
}

function BrandGlyph() {
  return (
    <span className="overlay-brand-glyph" aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}

function Waveform({ active }: { active: boolean }) {
  return (
    <div className={`overlay-waveform${active ? " active" : ""}`} aria-hidden="true">
      {waveformBars.map((height, index) => (
        <span key={height + index} style={{ height: `${height}%`, animationDelay: `${index * 45}ms` }} />
      ))}
    </div>
  );
}

function OverlayApp() {
  const { status, error, now } = useDesktopStatus();
  const [dismissedAt, setDismissedAt] = useState(0);
  const currentState: OverlayState = error ? "offline" : isOverlayState(status.status) ? status.status : "offline";
  const copy = stateCopy[currentState];
  const transcriptAge = status.updated_at > 0 ? now / 1000 - status.updated_at : Number.POSITIVE_INFINITY;
  const hasFreshTranscript = Boolean(status.transcript && transcriptAge < 4);
  const isExpanded =
    currentState !== "armed" && currentState !== "offline"
      ? status.updated_at > dismissedAt
      : hasFreshTranscript && status.updated_at > dismissedAt;
  const detail = error ? "The local status endpoint is unavailable" : status.detail || copy.detail;
  const latestTranscript = status.transcript || "";

  useEffect(() => {
    if (!isExpanded || currentState !== "pasting") return;
    const timer = window.setTimeout(() => setDismissedAt(status.updated_at), 2600);
    return () => window.clearTimeout(timer);
  }, [currentState, isExpanded, status.updated_at]);

  return (
    <main className="overlay-page">
      <section className={`overlay-shell ${isExpanded ? "expanded" : "compact"} state-${currentState}`} aria-live="polite">
        <header className="overlay-header">
          <div className="overlay-brand">
            <BrandGlyph />
            <span>VA</span>
          </div>
          <div className="overlay-connection">
            <span className="overlay-connection-dot" />
            {error ? "LOCAL OFFLINE" : "LOCAL"}
          </div>
          {isExpanded && (
            <button className="overlay-icon-button" onClick={() => setDismissedAt(status.updated_at)} type="button" aria-label="Collapse overlay">
              <span aria-hidden="true">−</span>
            </button>
          )}
        </header>

        <div className="overlay-status-row">
          <span className="overlay-status-mark" aria-hidden="true" />
          <div>
            <p className="overlay-eyebrow">{copy.eyebrow}</p>
            <h1>{copy.title}</h1>
          </div>
        </div>

        {isExpanded && (
          <div className="overlay-body">
            <p className="overlay-detail">{detail}</p>
            <Waveform active={currentState === "listening"} />
            {latestTranscript && (
              <div className="overlay-transcript">
                <span>LAST PHRASE</span>
                <p>{latestTranscript}</p>
              </div>
            )}
            {currentState === "error" || error ? (
              <p className="overlay-error" role="alert">{status.detail || "Check the tray companion and local API."}</p>
            ) : (
              <div className="overlay-meta">
                <span>{currentState === "listening" ? "MIC INPUT" : "MONGOLIAN"}</span>
                <span>{currentState === "listening" ? "LIVE" : "STT READY"}</span>
              </div>
            )}
          </div>
        )}

        <footer className="overlay-footer">
          <span>{isExpanded ? "Win + Alt" : "Hold to dictate"}</span>
          <a href="/" target="_blank" rel="noreferrer">Control panel <span aria-hidden="true">↗</span></a>
        </footer>
      </section>
    </main>
  );
}

export default OverlayApp;
