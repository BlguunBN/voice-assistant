import { useEffect, useMemo, useState } from "react";
import { useDesktopStatus } from "./hooks/useDesktopStatus";

export type WaveformMode = "listening" | "processing" | "thinking" | "speaking";

const bars = [0.34, 0.55, 0.78, 1, 0.68, 0.46, 0.82, 0.58, 0.36];
const copy: Record<string, string> = {
  listening: "Listening", transcribing: "Transcribing", thinking: "Thinking", speaking: "Speaking",
  success: "Text pasted", pasting: "Text pasted", error: "Could not dictate", offline: "Offline",
};

/** Shared minimal waveform. `amplitude` is reserved for a future microphone meter. */
export function Waveform({ mode, amplitude }: { mode: WaveformMode; amplitude?: number }) {
  const style = { "--amplitude": amplitude === undefined ? 1 : Math.max(0, Math.min(1, amplitude)) } as React.CSSProperties;
  return <div className={`wispr-waveform ${mode}`} style={style} aria-hidden="true">
    {bars.map((height, index) => <span key={index} style={{ "--bar": height, animationDelay: `${index * -90}ms` } as React.CSSProperties} />)}
  </div>;
}

function modeFor(state: string): WaveformMode {
  if (state === "transcribing") return "processing";
  if (state === "thinking") return "thinking";
  if (state === "speaking") return "speaking";
  return "listening";
}

function OverlayApp() {
  const { status, error, now } = useDesktopStatus();
  const state = error ? "error" : copy[status.status] ? status.status : "armed";
  const [fading, setFading] = useState(false);
  const age = now / 1000 - status.updated_at;
  const visible = state !== "armed" && state !== "offline" && (state !== "success" && state !== "pasting" ? true : age < 1.6);
  const message = error ? "Status unavailable" : status.detail || copy[state] || "Ready";

  useEffect(() => {
    setFading(false);
    if (state !== "success" && state !== "pasting") return;
    const timer = window.setTimeout(() => setFading(true), 1150);
    return () => window.clearTimeout(timer);
  }, [state, status.updated_at]);

  const content = useMemo(() => {
    if (state === "success" || state === "pasting") return <span className="wispr-check" aria-label="Text pasted">✓</span>;
    if (state === "error") return <><span className="wispr-error">!</span><span className="wispr-message">{message}</span></>;
    return <Waveform mode={modeFor(state)} />;
  }, [state, message]);

  if (!visible) return null;
  return <main className={`overlay-page ${fading ? "fading" : ""}`} aria-live="polite"><section className="wispr-pill">{content}</section></main>;
}

export default OverlayApp;
