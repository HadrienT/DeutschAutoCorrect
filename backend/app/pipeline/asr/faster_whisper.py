"""faster-whisper backend, configured to keep learner errors rather than fix them."""
from __future__ import annotations

from pathlib import Path

from ...models import Segment, Word
from .base import ProgressCb


class FasterWhisperAsr:
    name = "faster-whisper"

    def __init__(self, model: str = "large-v3", device: str = "auto", compute_type: str = "default"):
        try:
            from faster_whisper import WhisperModel  # lazy: heavy dependency
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("faster-whisper n'est pas installé (pip install -e .[asr])") from e
        self._model = WhisperModel(model, device=device, compute_type=compute_type)
        self.name = f"faster-whisper:{model}"

    def transcribe(self, wav_path: Path, progress: ProgressCb | None = None) -> list[Segment]:
        kwargs = dict(
            word_timestamps=True,
            condition_on_previous_text=False,  # avoid LM drift that "repairs" mistakes
            initial_prompt=None,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            beam_size=5,
            temperature=0.0,
            no_speech_threshold=0.6,
        )
        try:  # per-segment language detection (german/french mix) when supported
            segs_iter, info = self._model.transcribe(str(wav_path), multilingual=True, **kwargs)
        except TypeError:  # pragma: no cover - older faster-whisper
            segs_iter, info = self._model.transcribe(str(wav_path), **kwargs)
        total = max(getattr(info, "duration", 0.0), 1e-6)
        out: list[Segment] = []
        for s in segs_iter:
            if getattr(s, "no_speech_prob", 0.0) > 0.8 and getattr(s, "avg_logprob", 0) < -1.0:
                continue  # hallucination on silence/noise
            words = [Word(text=w.word.strip(), start=float(w.start), end=float(w.end),
                          prob=float(w.probability)) for w in (s.words or []) if w.word.strip()]
            text = s.text.strip()
            if not text:
                continue
            out.append(Segment(id=f"s{len(out) + 1}", start=float(s.start), end=float(s.end),
                               text=text, words=words,
                               no_speech_prob=float(getattr(s, "no_speech_prob", 0.0))))
            if progress:
                progress(min(1.0, float(s.end) / total))
        return out
