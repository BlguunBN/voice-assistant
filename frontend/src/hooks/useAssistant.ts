import { useCallback, useRef, useState, type RefObject } from "react";
import {
  chat,
  synthesize,
  transcribe,
  type ConversationLanguage,
  type TranscriptionLanguage,
} from "../api/client";
import { encodeWav, mergeFloat32Chunks } from "../audio/wav";
import type { AssistantStatus, VoiceMessage } from "../types";

type Recorder = {
  context: AudioContext;
  stream: MediaStream;
  source: MediaStreamAudioSourceNode;
  processor: ScriptProcessorNode;
  mute: GainNode;
  samples: Float32Array[];
};

type AssistantOptions = {
  microphoneId: string;
  voiceId: string;
  language: TranscriptionLanguage;
  audioRef: RefObject<HTMLAudioElement | null>;
};

function getAudioContext(): AudioContext {
  const browserWindow = window as typeof window & {
    webkitAudioContext?: typeof AudioContext;
  };
  const AudioContextClass = window.AudioContext || browserWindow.webkitAudioContext;
  if (!AudioContextClass) throw new Error("Энэ browser audio recording-ийг дэмжихгүй байна.");
  return new AudioContextClass();
}

export function useAssistant({ microphoneId, voiceId, language, audioRef }: AssistantOptions) {
  const recorderRef = useRef<Recorder | null>(null);
  const [status, setStatus] = useState<AssistantStatus>("ready");
  const [messages, setMessages] = useState<VoiceMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [inputLevel, setInputLevel] = useState(0);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);

  const playAudio = useCallback(async (audio: Blob) => {
    const element = audioRef.current;
    if (!element) throw new Error("Audio player is unavailable.");
    const url = URL.createObjectURL(audio);
    element.src = url;
    try {
      await element.play();
      await new Promise<void>((resolve, reject) => {
        const finish = () => resolve();
        const fail = () => reject(new Error("TTS audio playback failed."));
        element.addEventListener("ended", finish, { once: true });
        element.addEventListener("error", fail, { once: true });
      });
    } finally {
      URL.revokeObjectURL(url);
      element.removeAttribute("src");
      element.load();
    }
  }, [audioRef]);

  const appendMessage = useCallback((role: VoiceMessage["role"], text: string) => {
    setMessages((current) => [
      ...current,
      { id: Date.now() + Math.random(), role, text, createdAt: new Date().toISOString() },
    ]);
  }, []);

  const runConversation = useCallback(async (
    message: string,
    detectedLanguage?: ConversationLanguage,
  ) => {
    const normalized = message.trim();
    if (!normalized) return;
    const startedAt = performance.now();
    setError(null);
    setStatus("processing");
    appendMessage("user", normalized);
    try {
      const responseLanguage = detectedLanguage ?? (language === "auto" ? "mn" : language);
      const response = await chat(normalized, responseLanguage);
      appendMessage("assistant", response);
      setStatus("speaking");
      const audio = await synthesize(
        response,
        responseLanguage === "mn" ? voiceId || undefined : undefined,
        responseLanguage,
      );
      setLatencyMs(Math.round(performance.now() - startedAt));
      await playAudio(audio);
      setStatus("ready");
    } catch (requestError) {
      setStatus("error");
      setError(requestError instanceof Error ? requestError.message : "Voice response failed.");
    }
  }, [appendMessage, language, playAudio, voiceId]);

  const startRecording = useCallback(async () => {
    if (recorderRef.current || status === "processing" || status === "speaking") return;
    try {
      setError(null);
      const audioConstraints: MediaTrackConstraints = {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      };
      if (microphoneId) audioConstraints.deviceId = { exact: microphoneId };
      const stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
      const context = getAudioContext();
      await context.resume();
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      const mute = context.createGain();
      mute.gain.value = 0;
      const samples: Float32Array[] = [];
      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0);
        samples.push(new Float32Array(input));
        let sum = 0;
        for (const sample of input) sum += sample * sample;
        setInputLevel(Math.min(1, Math.sqrt(sum / input.length) * 3));
      };
      source.connect(processor);
      processor.connect(mute);
      mute.connect(context.destination);
      recorderRef.current = { context, stream, source, processor, mute, samples };
      setStatus("listening");
    } catch (recordingError) {
      setStatus("error");
      setError(recordingError instanceof Error ? recordingError.message : "Microphone access failed.");
    }
  }, [microphoneId, status]);

  const stopRecording = useCallback(async () => {
    const recorder = recorderRef.current;
    if (!recorder) return;
    recorderRef.current = null;
    recorder.processor.disconnect();
    recorder.source.disconnect();
    recorder.mute.disconnect();
    recorder.stream.getTracks().forEach((track) => track.stop());
    await recorder.context.close();
    setInputLevel(0);
    const samples = mergeFloat32Chunks(recorder.samples);
    if (samples.length === 0) {
      setStatus("ready");
      return;
    }
    setStatus("processing");
    try {
      const result = await transcribe(encodeWav(samples, recorder.context.sampleRate), language);
      await runConversation(result.transcript, result.detected_language);
    } catch (requestError) {
      setStatus("error");
      setError(requestError instanceof Error ? requestError.message : "Transcription failed.");
    }
  }, [language, runConversation]);

  const sendText = useCallback((message: string) => {
    void runConversation(message);
  }, [runConversation]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
    setStatus("ready");
    setLatencyMs(null);
  }, []);

  return {
    status,
    messages,
    error,
    inputLevel,
    latencyMs,
    startRecording,
    stopRecording,
    sendText,
    clearMessages,
  };
}
