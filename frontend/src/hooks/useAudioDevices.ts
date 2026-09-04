import { useCallback, useEffect, useState } from "react";
import type { AudioDevice } from "../types";

function normalizeDevices(devices: MediaDeviceInfo[]): AudioDevice[] {
  return devices
    .filter((device) => device.kind === "audioinput" || device.kind === "audiooutput")
    .map((device, index) => ({
      deviceId: device.deviceId,
      kind: device.kind,
      label: device.label || `${device.kind === "audioinput" ? "Microphone" : "Speaker"} ${index + 1}`,
    }));
}

export function useAudioDevices() {
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [permissionError, setPermissionError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) {
      setPermissionError("Энэ browser audio төхөөрөмж сонгохыг дэмжихгүй байна.");
      return;
    }
    const listed = await navigator.mediaDevices.enumerateDevices();
    setDevices(normalizeDevices(listed));
  }, []);

  const enableMicrophone = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setPermissionError("Энэ browser microphone ашиглахыг дэмжихгүй байна.");
      return false;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setPermissionError(null);
      await refresh();
      return true;
    } catch (error) {
      setPermissionError(error instanceof Error ? error.message : "Microphone permission denied.");
      return false;
    }
  }, [refresh]);

  useEffect(() => {
    void refresh();
    const handleDeviceChange = () => void refresh();
    navigator.mediaDevices?.addEventListener("devicechange", handleDeviceChange);
    return () => navigator.mediaDevices?.removeEventListener("devicechange", handleDeviceChange);
  }, [refresh]);

  return {
    inputDevices: devices.filter((device) => device.kind === "audioinput"),
    outputDevices: devices.filter((device) => device.kind === "audiooutput"),
    permissionError,
    refresh,
    enableMicrophone,
  };
}
