from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


class AudioDeviceError(RuntimeError):
    """Raised when an audio device cannot be discovered or selected."""


@dataclass(frozen=True)
class AudioDevice:
    """A PortAudio device with the capabilities needed by the assistant."""

    index: int
    name: str
    host_api: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: int

    @property
    def is_input(self) -> bool:
        return self.max_input_channels > 0

    @property
    def is_output(self) -> bool:
        return self.max_output_channels > 0

    def label(self) -> str:
        direction = []
        if self.is_input:
            direction.append(f"{self.max_input_channels} in")
        if self.is_output:
            direction.append(f"{self.max_output_channels} out")
        return f"[{self.index}] {self.name} ({self.host_api}; {', '.join(direction)})"


class AudioDeviceManager:
    """Discover and resolve configured input and output PortAudio devices."""

    def __init__(self, input_device: int | str | None = None, output_device: int | str | None = None) -> None:
        self.input_device = input_device
        self.output_device = output_device

    @staticmethod
    def _sounddevice() -> Any:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioDeviceError("sounddevice is required for microphone capture") from exc
        return sd

    def list_devices(self) -> list[AudioDevice]:
        sd = self._sounddevice()
        try:
            raw_devices = sd.query_devices()
            host_apis = sd.query_hostapis()
        except Exception as exc:
            raise AudioDeviceError(f"Unable to query audio devices: {exc}") from exc
        devices: list[AudioDevice] = []
        for index, raw in enumerate(raw_devices):
            host_api_index = int(raw.get("hostapi", -1))
            host_api = host_apis[host_api_index].get("name", "unknown") if host_api_index >= 0 else "unknown"
            devices.append(
                AudioDevice(
                    index=index,
                    name=str(raw.get("name", "unknown")),
                    host_api=str(host_api),
                    max_input_channels=int(raw.get("max_input_channels", 0)),
                    max_output_channels=int(raw.get("max_output_channels", 0)),
                    default_samplerate=int(float(raw.get("default_samplerate", 0))),
                )
            )
        return devices

    def selected(self, direction: Literal["input", "output"]) -> AudioDevice:
        configured = self.input_device if direction == "input" else self.output_device
        devices = [device for device in self.list_devices() if getattr(device, f"is_{direction}")]
        if not devices:
            raise AudioDeviceError(f"No {direction} audio devices are available")

        if configured is not None:
            return self._resolve_configured(configured, devices, direction)

        sd = self._sounddevice()
        try:
            defaults = sd.default.device
            default_index = int(defaults[0 if direction == "input" else 1])
        except (TypeError, ValueError, IndexError, AttributeError):
            default_index = -1
        for device in devices:
            if device.index == default_index:
                return device
        return devices[0]

    @staticmethod
    def _resolve_configured(
        configured: int | str,
        devices: list[AudioDevice],
        direction: str,
    ) -> AudioDevice:
        if isinstance(configured, int):
            for device in devices:
                if device.index == configured:
                    return device
            raise AudioDeviceError(f"Configured {direction} device index {configured} is unavailable")

        query = str(configured).strip().lower()
        if query.isdigit():
            return AudioDeviceManager._resolve_configured(int(query), devices, direction)
        matches = [device for device in devices if query in device.name.lower()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise AudioDeviceError(f"Configured {direction} device {configured!r} is unavailable")
        labels = ", ".join(str(device.index) for device in matches)
        raise AudioDeviceError(
            f"Configured {direction} device {configured!r} matches multiple devices: {labels}"
        )

    def describe(self) -> tuple[AudioDevice, AudioDevice, list[AudioDevice]]:
        devices = self.list_devices()
        return self.selected("input"), self.selected("output"), devices
