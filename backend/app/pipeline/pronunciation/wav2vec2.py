"""Acoustic phoneme recognition (wav2vec2 CTC, espeak IPA vocabulary), word by word."""
from __future__ import annotations

from pathlib import Path

from ...models import Segment
from ..audio import read_wav
from .base import WordPhonemes
from .g2p import expected_phonemes

PAD = 0.06  # seconds of context around each word


class Wav2Vec2Phonemes:
    name = "wav2vec2"

    def __init__(self, model: str = "facebook/wav2vec2-xlsr-53-espeak-cv-ft", device: str = "auto"):
        try:
            import torch  # lazy: heavy
            from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("torch/transformers requis (pip install -e .[pron])") from e
        self._torch = torch
        self._device = ("cuda" if torch.cuda.is_available() else "cpu") if device == "auto" else device
        self._proc = Wav2Vec2Processor.from_pretrained(model)
        self._model = Wav2Vec2ForCTC.from_pretrained(model).to(self._device).eval()
        self.name = f"wav2vec2:{model.split('/')[-1]}"

    def _recognise(self, chunk, sr: int) -> list[str]:
        torch = self._torch
        inputs = self._proc(chunk, sampling_rate=sr, return_tensors="pt")
        with torch.no_grad():
            logits = self._model(inputs.input_values.to(self._device)).logits
        ids = torch.argmax(logits, dim=-1)
        return self._proc.batch_decode(ids)[0].split()

    def analyze(self, wav_path: Path, segments: list[Segment]) -> list[WordPhonemes]:
        samples, sr = read_wav(wav_path)
        out: list[WordPhonemes] = []
        for seg in segments:
            for i, w in enumerate(seg.words):
                exp = expected_phonemes(w.text)
                a, b = max(0, int((w.start - PAD) * sr)), min(len(samples), int((w.end + PAD) * sr))
                if not exp or b - a < sr * 0.08:
                    continue
                obs = self._recognise(samples[a:b], sr)
                out.append(WordPhonemes(seg.id, i, w.text, w.start, w.end, exp, obs))
        return out
