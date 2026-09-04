import { describe, expect, it } from "vitest";
import { encodeWav, mergeFloat32Chunks } from "./wav";

describe("browser WAV encoder", () => {
  it("merges recorded chunks without changing sample order", () => {
    const merged = mergeFloat32Chunks([new Float32Array([0.1, 0.2]), new Float32Array([-0.3])]);
    expect(merged[0]).toBeCloseTo(0.1, 6);
    expect(merged[1]).toBeCloseTo(0.2, 6);
    expect(merged[2]).toBeCloseTo(-0.3, 6);
  });

  it("creates mono 16-bit PCM WAV audio at 16 kHz", async () => {
    const samples = new Float32Array(480);
    samples[120] = 0.5;
    samples[240] = -0.5;
    samples[360] = 1;
    const wav = encodeWav(samples, 48_000);
    const bytes = new Uint8Array(await wav.arrayBuffer());
    const view = new DataView(bytes.buffer);

    expect(wav.type).toBe("audio/wav");
    expect(bytes.length).toBe(44 + 160 * 2);
    expect(String.fromCharCode(...bytes.slice(0, 4))).toBe("RIFF");
    expect(String.fromCharCode(...bytes.slice(8, 12))).toBe("WAVE");
    expect(view.getUint16(22, true)).toBe(1);
    expect(view.getUint32(24, true)).toBe(16_000);
    expect(view.getUint16(34, true)).toBe(16);
  });
});
