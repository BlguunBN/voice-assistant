# Mongolian and English STT options

Research date: 2026-09-05. No models were downloaded or run for this review.

## Current baseline

`Blgn94/whisper-small-mn-v3` is a 244M-parameter Apache-2.0 Whisper-small
fine-tune for Cyrillic Mongolian. Its model card reports 21.33% raw and 19.67%
normalized WER on a custom text-disjoint clean evaluation set. This is not
speaker-disjoint, so the result should not be treated as a universal production
benchmark. It is Mongolian-only, despite Whisper's multilingual base.

Source: <https://huggingface.co/Blgn94/whisper-small-mn-v3>

## Candidates

| Purpose | Model | Evidence | Compatibility and limitations |
| --- | --- | --- | --- |
| Mongolian candidate to benchmark | `orgilj/moonshine-mn` | 48.7M parameters; Apache-2.0; its card reports 11.88% WER on Mongolian Common Voice. | Transformers `MoonshineForConditionalGeneration` with a custom Mongolian BPE tokenizer. The card does not state a comparable split or normalization, so its score does not prove it beats the baseline. Mongolian-only; not compatible with faster-whisper. |
| English candidate to benchmark | `Qwen/Qwen3-ASR-0.6B-hf` | Official 0.6B model, Apache-2.0, offline and streaming support. | Requires Transformers 5.13 or newer and Qwen's multimodal model/processor. English is supported, but Mongolian is not listed; it cannot replace the current model alone. |
| English quality alternative | `Qwen/Qwen3-ASR-1.7B-hf` | Official larger Qwen ASR variant. | Same Mongolian limitation; probably unsuitable for the project's 4 GB RTX 3050 Laptop GPU without further memory testing. |

Sources: <https://huggingface.co/orgilj/moonshine-mn>,
<https://huggingface.co/Qwen/Qwen3-ASR-0.6B-hf>,
<https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf>

## Rejected candidates

- `tugstugi/wav2vec2-large-xlsr-53-mongolian` reports 42.8% WER on Common Voice
  Mongolian and is not a credible improvement over the present baseline.
  Source: <https://huggingface.co/tugstugi/wav2vec2-large-xlsr-53-mongolian>
- `Blgn94/whisper-large-v3-turbo-mn-lora` reports 27.4% WER on a 200-clip,
  Common-Voice-dominant evaluation, which is worse on paper than the current
  baseline's reported result. Source:
  <https://huggingface.co/Blgn94/whisper-large-v3-turbo-mn-lora>
- Base `openai/whisper-large-v3-turbo` supports both English and Mongolian, but
  the above Mongolian fine-tune reports the base at 98.2% WER on its held-out
  subset. It should not replace the Mongolian fine-tune without local testing.

## Recommendation

Keep the current Whisper model as the Mongolian baseline. If implementation is
authorized, add opt-in language routing and a fixed, locally owned benchmark:
benchmark Moonshine-MN against the baseline for Mongolian, and Qwen ASR against
the baseline for English. Evaluate WER/CER, microphone noise, latency, and VRAM
before making either model the default. This routing approach needs a dependency
upgrade and a separate English model download; neither is part of this research
note.
