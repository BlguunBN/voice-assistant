import type { DesktopStatus, Health } from "../types";

export type ConversationLanguage = "mn" | "en";
export type TranscriptionLanguage = ConversationLanguage | "auto";

const API_PREFIX = "/api";

async function parseError(response: Response): Promise<Error> {
  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = (await response.json()) as { detail?: string };
    if (body.detail) detail = body.detail;
  } catch {
    // Keep the HTTP status when the response is not JSON.
  }
  return new Error(detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, init);
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}

export async function getHealth(): Promise<Health> {
  return request<Health>("/health");
}

export async function getDesktopStatus(): Promise<DesktopStatus> {
  return request<DesktopStatus>("/desktop/status");
}

export async function getVoices(): Promise<string[]> {
  const body = await request<{ voices: string[] }>("/voices");
  return body.voices;
}

export async function transcribe(audio: Blob, language: TranscriptionLanguage = "mn"): Promise<string> {
  const form = new FormData();
  form.append("file", audio, "browser-recording.wav");
  form.append("language", language);
  const body = await request<{ transcript: string }>("/stt", {
    method: "POST",
    body: form,
  });
  return body.transcript;
}

export async function chat(message: string, language: ConversationLanguage = "mn"): Promise<string> {
  const body = await request<{ response: string }>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, language }),
  });
  return body.response;
}

export async function synthesize(
  text: string,
  speakerId: string | undefined,
  language: ConversationLanguage = "mn",
): Promise<Blob> {
  const response = await fetch(`${API_PREFIX}/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, speaker_id: speakerId || null, language }),
  });
  if (!response.ok) throw await parseError(response);
  return response.blob();
}
