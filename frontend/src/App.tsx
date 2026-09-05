import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  getDesktopPreferences,
  getVoices,
  updateDesktopPreferences,
  type TranscriptionLanguage,
} from "./api/client";
import { useAssistant } from "./hooks/useAssistant";
import { useAudioDevices } from "./hooks/useAudioDevices";
import { useDesktopStatus } from "./hooks/useDesktopStatus";
import { useHealth } from "./hooks/useHealth";
import type { AssistantStatus, AudioDevice, DesktopLanguage, VoiceMessage } from "./types";

const statusLabels: Record<AssistantStatus, string> = {
  ready: "Ready",
  listening: "Listening",
  processing: "Processing",
  speaking: "Speaking",
  error: "Needs attention",
};

const desktopLanguageLabels: Record<DesktopLanguage, string> = {
  mn: "Монгол",
  en: "English",
  auto: "Auto detect",
};
function deviceLabel(device: AudioDevice): string {
  return device.label || (device.kind === "audioinput" ? "Microphone" : "Speaker");
}

function StatusDot({ active = false }: { active?: boolean }) {
  return <span className={`status-dot${active ? " active" : ""}`} aria-hidden="true" />;
}

function StatusCard({ label, value, active = false }: { label: string; value: string; active?: boolean }) {
  return (
    <div className="status-card">
      <span className="eyebrow"><StatusDot active={active} />{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MessageList({ messages, language }: { messages: VoiceMessage[]; language: TranscriptionLanguage }) {
  if (messages.length === 0) {
    return (
      <div className="empty-state">
        <span className="empty-orbit" aria-hidden="true" />
        <h2>{language === "mn" ? "Танд туслахад бэлэн байна" : "Ready when you are"}</h2>
        <p>{language === "mn" ? "Доорх товчийг дарж бариад Монгол хэлээр ярьна уу." : "Hold the button below and speak in English."}</p>
      </div>
    );
  }
  return (
    <div className="message-list" aria-live="polite">
      {messages.map((message) => (
        <article className={`message ${message.role}`} key={message.id}>
          <span className="message-role">{message.role === "user" ? "You" : "Assistant"}</span>
          <p>{message.text}</p>
        </article>
      ))}
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  devices,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  devices: AudioDevice[];
  placeholder: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{placeholder}</option>
        {devices.map((device) => (
          <option value={device.deviceId} key={device.deviceId}>
            {deviceLabel(device)}
          </option>
        ))}
      </select>
    </label>
  );
}

function App() {
  const [view, setView] = useState<"assistant" | "audio" | "system">("assistant");
  const [microphoneId, setMicrophoneId] = useState(() => localStorage.getItem("voice-assistant.microphone") ?? "");
  const [speakerId, setSpeakerId] = useState(() => localStorage.getItem("voice-assistant.speaker") ?? "");
  const [voiceId, setVoiceId] = useState(() => localStorage.getItem("voice-assistant.voice") ?? "");
  const [language, setLanguage] = useState<TranscriptionLanguage>(() => {
    const stored = localStorage.getItem("voice-assistant.language");
    return stored === "mn" || stored === "en" || stored === "auto" ? stored : "mn";
  });
  const [desktopLanguage, setDesktopLanguage] = useState<DesktopLanguage>(() => {
    const stored = localStorage.getItem("voice-assistant.desktop-language");
    return stored === "mn" || stored === "en" || stored === "auto" ? stored : "auto";
  });
  const [desktopPreferenceError, setDesktopPreferenceError] = useState<string | null>(null);
  const [voices, setVoices] = useState<string[]>([]);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [speakerSupported, setSpeakerSupported] = useState(true);
  const [draft, setDraft] = useState("");
  const audioRef = useRef<HTMLAudioElement>(null);
  const { health, error: healthError } = useHealth();
  const { status: desktopStatus, error: desktopStatusError } = useDesktopStatus();
  const { inputDevices, outputDevices, permissionError, enableMicrophone, refresh } = useAudioDevices();
  const assistant = useAssistant({ microphoneId, voiceId, language, audioRef });

  useEffect(() => {
    localStorage.setItem("voice-assistant.microphone", microphoneId);
  }, [microphoneId]);

  useEffect(() => {
    localStorage.setItem("voice-assistant.speaker", speakerId);
  }, [speakerId]);

  useEffect(() => {
    localStorage.setItem("voice-assistant.voice", voiceId);
  }, [voiceId]);
  useEffect(() => {
    localStorage.setItem("voice-assistant.language", language);
  }, [language]);

  useEffect(() => {
    localStorage.setItem("voice-assistant.desktop-language", desktopLanguage);
  }, [desktopLanguage]);

  useEffect(() => {
    let active = true;
    void getDesktopPreferences()
      .then((preferences) => {
        if (active) setDesktopLanguage(preferences.selected_language);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    let active = true;
    void getVoices()
      .then((nextVoices) => {
        if (!active) return;
        setVoices(nextVoices);
        setVoiceError(null);
      })
      .catch((error) => {
        if (active) setVoiceError(error instanceof Error ? error.message : "Voice discovery failed.");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const element = audioRef.current as (HTMLAudioElement & { setSinkId?: (id: string) => Promise<void> }) | null;
    if (!element) return;
    if (!element.setSinkId) {
      setSpeakerSupported(false);
      return;
    }
    setSpeakerSupported(true);
    if (speakerId) void element.setSinkId(speakerId).catch(() => undefined);
  }, [speakerId]);

  useEffect(() => {
    const isTyping = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      return target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.tagName === "SELECT";
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.code !== "Space" || event.repeat || isTyping(event)) return;
      event.preventDefault();
      void assistant.startRecording();
    };
    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.code !== "Space" || isTyping(event)) return;
      event.preventDefault();
      void assistant.stopRecording();
    };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [assistant.startRecording, assistant.stopRecording]);

  const apiOnline = Boolean(health && !healthError);
  const selectedVoice = useMemo(() => voiceId || voices[0] || "", [voiceId, voices]);
  const selectedInputLabel = inputDevices.find((device) => device.deviceId === microphoneId)?.label ?? "Default microphone";
  const selectedOutputLabel = outputDevices.find((device) => device.deviceId === speakerId)?.label ?? "Default speaker";

  const submitText = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft.trim()) return;
    assistant.sendText(draft);
    setDraft("");
  };

  const handleEnableMicrophone = async () => {
    await enableMicrophone();
  };

  const handleDesktopLanguageChange = (value: DesktopLanguage) => {
    setDesktopLanguage(value);
    setDesktopPreferenceError(null);
    void updateDesktopPreferences(value).catch((error) => {
      setDesktopPreferenceError(error instanceof Error ? error.message : "Desktop language preference failed.");
    });
  };

  const renderAudioSettings = () => (
    <section className="panel settings-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Audio routing</span>
          <h2>Төхөөрөмж сонгох</h2>
        </div>
        <button className="button ghost" onClick={() => void refresh()} type="button">Refresh</button>
      </div>
      <div className="field-grid">
        <SelectField label="Microphone" value={microphoneId} onChange={setMicrophoneId} devices={inputDevices} placeholder="Default microphone" />
        <SelectField label="Speaker" value={speakerId} onChange={setSpeakerId} devices={outputDevices} placeholder="Default speaker" />
      </div>
      <div className="settings-actions">
        <button className="button secondary" onClick={() => void handleEnableMicrophone()} type="button">Enable microphone</button>
        <span className="muted">Selections save automatically on this device.</span>
      </div>
      {permissionError && <p className="inline-error">{permissionError}</p>}
      {!speakerSupported && <p className="inline-warning">Энэ browser speaker сонголтыг дэмжихгүй тул системийн default speaker ашиглана.</p>}
    </section>
  );

  const renderSystem = () => (
    <section className="panel system-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Runtime control</span>
          <h2>Системийн төлөв</h2>
        </div>
        <a className="button ghost" href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">Open API docs</a>
      </div>
      <div className="status-grid">
        <StatusCard label="API" value={apiOnline ? "Online" : "Offline"} active={apiOnline} />
        <StatusCard label="STT model" value={health?.stt_loaded ? "Loaded" : "Unavailable"} active={Boolean(health?.stt_loaded)} />
        <StatusCard label="TTS model" value={health?.tts_loaded ? "Loaded" : "Unavailable"} active={Boolean(health?.tts_loaded)} />
        <StatusCard label="English TTS" value={health?.english_tts_loaded ? "Loaded" : "Lazy"} active={Boolean(health?.english_tts_loaded)} />
        <StatusCard label="Exposure" value={health?.external_network_exposure ? "External" : "Loopback only"} active={!health?.external_network_exposure} />
      </div>
      <dl className="detail-list">
        <div><dt>Agent bridge</dt><dd>{health?.agent_bridge ?? "—"}</dd></div>
        <div><dt>Reasoning</dt><dd>{health?.llm_provider ?? "—"}{health?.llm_model ? " · " + health.llm_model : ""}</dd></div>
        <div><dt>Bind host</dt><dd>{health?.bind_host ?? "—"}</dd></div>
        <div><dt>Last turn</dt><dd>{assistant.latencyMs ? `${assistant.latencyMs} ms` : "—"}</dd></div>
        <div><dt>Voice count</dt><dd>{voices.length || "—"}</dd></div>
      </dl>
      {healthError && <p className="inline-error">API unavailable: {healthError}</p>}
      {voiceError && <p className="inline-warning">Voice list unavailable: {voiceError}</p>}
    </section>
  );

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true">VA</div>
        <div>
          <p className="brand-name">Mongolian Voice Assistant</p>
          <p className="brand-subtitle">Local speech control center</p>
        </div>
        <div className={`connection-pill${apiOnline ? " online" : ""}`}><StatusDot active={apiOnline} />API {apiOnline ? "Online" : "Offline"}</div>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <span className="eyebrow">Workspace</span>
          <nav className="nav-list" aria-label="Main navigation">
            <button className={view === "assistant" ? "nav-item active" : "nav-item"} onClick={() => setView("assistant")} type="button"><span>01</span>Assistant</button>
            <button className={view === "audio" ? "nav-item active" : "nav-item"} onClick={() => setView("audio")} type="button"><span>02</span>Audio setup</button>
            <button className={view === "system" ? "nav-item active" : "nav-item"} onClick={() => setView("system")} type="button"><span>03</span>System</button>
          </nav>
          <div className="sidebar-note">
            <span className="eyebrow">Hybrid mode</span>
            <p>Audio STT/TTS stays local. Chat text is sent to configured NVIDIA NIM.</p>
          </div>
        </aside>

        <main className="main-content">
          {view === "assistant" && (
            <>
              <div className="page-heading">
                <div><span className="eyebrow">Conversation</span><h1>Ярилцъя.</h1></div>
                <span className={`state-label ${assistant.status}`}>{statusLabels[assistant.status]}</span>
              </div>
              <section className="conversation-panel panel">
                <MessageList messages={assistant.messages} language={language} />
                {assistant.error && <div className="error-banner" role="alert">{assistant.error}</div>}
                <div className="talk-zone">
                  <div className="level-track" aria-label={`Input level ${Math.round(assistant.inputLevel * 100)} percent`}><span style={{ width: `${assistant.inputLevel * 100}%` }} /></div>
                  <button
                    className={`talk-button ${assistant.status === "listening" ? "recording" : ""}`}
                    onPointerDown={() => void assistant.startRecording()}
                    onPointerUp={() => void assistant.stopRecording()}
                    onPointerLeave={() => void assistant.stopRecording()}
                    onPointerCancel={() => void assistant.stopRecording()}
                    type="button"
                    aria-label="Hold to talk"
                  >
                    <span className="talk-ring" aria-hidden="true"><span /></span>
                    <strong>{assistant.status === "listening" ? "Release to send" : "Hold to talk"}</strong>
                    <small>or hold Space</small>
                  </button>
                </div>
                <form className="text-form" onSubmit={submitText}>
                  <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Type a message instead..." aria-label="Type a message" />
                  <button className="button primary" type="submit" disabled={!draft.trim() || assistant.status === "processing" || assistant.status === "speaking"}>Send</button>
                </form>
              </section>
              <div className="quick-summary">
                <div><span className="eyebrow">Microphone</span><strong>{selectedInputLabel}</strong></div>
                <div><span className="eyebrow">Speaker</span><strong>{selectedOutputLabel}</strong></div>
                <div><span className="eyebrow">Latency</span><strong>{assistant.latencyMs ? `${assistant.latencyMs} ms` : "—"}</strong></div>
                <button className="button ghost" onClick={assistant.clearMessages} type="button">Clear chat</button>
              </div>
            </>
          )}
          {view === "audio" && renderAudioSettings()}
          {view === "system" && renderSystem()}
        </main>

        <aside className="right-rail">
          <section className="rail-section">
            <span className="eyebrow">Runtime</span>
            <StatusCard label="Speech to text" value={health?.stt_loaded ? "Ready" : "Waiting"} active={Boolean(health?.stt_loaded)} />
            <StatusCard label="Text to speech" value={health?.tts_loaded ? "Ready" : "Waiting"} active={Boolean(health?.tts_loaded)} />
            <StatusCard label="Reasoning model" value={health?.llm_configured ? "Ready" : "Configure key"} active={Boolean(health?.llm_configured)} />
            <StatusCard label="Voice activity" value={assistant.status === "listening" ? "Listening" : "Armed"} active={assistant.status !== "error"} />
          </section>
          <section className="rail-section compact-controls">
            <label className="field">
              <span>Dictation language</span>
              <select value={desktopLanguage} onChange={(event) => handleDesktopLanguageChange(event.target.value as DesktopLanguage)}>
                <option value="mn">Монгол</option>
                <option value="en">English</option>
                <option value="auto">Auto detect</option>
              </select>
            </label>
            <div className="desktop-status" aria-live="polite">
              <div className="section-heading">
                <span className="eyebrow"><StatusDot active={!desktopStatusError && desktopStatus.status !== "offline"} />Desktop dictation</span>
                <strong>{desktopStatusError ? "Offline" : desktopStatus.status}</strong>
              </div>
              <p className="muted">Selected: {desktopLanguageLabels[desktopLanguage]}{desktopStatus.detected_language ? " · Detected: " + desktopLanguageLabels[desktopStatus.detected_language] : ""}</p>
            </div>
            {desktopPreferenceError && <p className="inline-error">Language preference unavailable: {desktopPreferenceError}</p>}
            <div className="section-heading"><span className="eyebrow">Conversation language</span></div>
            <label className="field"><span className="sr-only">Conversation language</span><select value={language} onChange={(event) => setLanguage(event.target.value as TranscriptionLanguage)}><option value="mn">Монгол</option><option value="en">English</option><option value="auto">Auto detect</option></select></label>
            <div className="section-heading"><span className="eyebrow">Speech output</span><span className="count-badge">{language === "mn" ? voices.length : 1}</span></div>
            <label className="field"><span>Voice</span><select disabled={language !== "mn"} value={language === "mn" ? selectedVoice : ""} onChange={(event) => setVoiceId(event.target.value)}><option value="">{language === "mn" ? "Default voice" : "Detected language voice"}</option>{voices.map((voice) => <option value={voice} key={voice}>{voice}</option>)}</select></label>
            <p className="muted">{language === "auto" ? "Whisper chooses Mongolian or English for each recording." : language === "en" ? "English uses the local default voice." : speakerSupported ? "Selected speaker is used for TTS playback." : "Browser speaker routing unavailable."}</p>
          </section>
        </aside>
      </div>
      <audio ref={audioRef} preload="none" />
    </div>
  );
}

export default App;
