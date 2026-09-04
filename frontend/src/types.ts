export type Health = {
  status: string;
  service: string;
  agent_bridge: string;
  llm_provider: string;
  llm_model: string | null;
  llm_configured: boolean;
  stt_loaded: boolean;
  tts_loaded: boolean;
  english_tts_loaded: boolean;
  bind_host: string;
  external_network_exposure: boolean;
};

export type DesktopStatus = {
  status: string;
  transcript: string | null;
  detail: string | null;
  updated_at: number;
};

export type VoiceMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
};

export type AssistantStatus = "ready" | "listening" | "processing" | "speaking" | "error";

export type AudioDevice = {
  deviceId: string;
  label: string;
  kind: MediaDeviceKind;
};
