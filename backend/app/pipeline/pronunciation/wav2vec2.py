"""Acoustic phoneme recognition (wav2vec2 CTC, espeak IPA vocabulary), segment by segment."""
from __future__ import annotations

import json
from pathlib import Path

from ...models import Segment
from ..audio import read_wav
from .base import WordPhonemes
from .compare import split_by_words, tokenize
from .g2p import expected_phonemes

PAD = 0.4  # seconds of context around each segment (ASR boundaries are approximate)
SPECIAL = {"<pad>", "<s>", "</s>", "<unk>", "|"}


def ctc_decode(ids: list[int], vocab: dict[int, str]) -> list[str]:
    """Greedy CTC: collapse repeats, then drop blanks and special tokens."""
    out: list[str] = []
    prev = None
    for i in ids:
        tok = vocab.get(i, "<unk>")
        if i != prev and tok not in SPECIAL and not tok.isdigit():  # digits: tone marks
            out.append(tok)
        prev = i
    return out


class Wav2Vec2Phonemes:
    name = "wav2vec2"

    def __init__(self, model: str = "facebook/wav2vec2-xlsr-53-espeak-cv-ft", device: str = "auto"):
        try:
            import torch  # lazy: heavy
            from huggingface_hub import hf_hub_download
            from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("torch/transformers requis (pip install -e .[pron])") from e
        self._torch = torch
        self._device = ("cuda" if torch.cuda.is_available() else "cpu") if device == "auto" else device
        # The model's tokenizer class needs `phonemizer` just to be instantiated; decoding CTC
        # output only takes the vocabulary.
        self._features = Wav2Vec2FeatureExtractor.from_pretrained(model)
        with open(hf_hub_download(model, "vocab.json"), encoding="utf-8") as f:
            self._vocab = {i: tok for tok, i in json.load(f).items()}
        self._model = Wav2Vec2ForCTC.from_pretrained(model).to(self._device).eval()
        self.name = f"wav2vec2:{model.split('/')[-1]}"

    def _recognise(self, chunk, sr: int) -> list[str]:
        torch = self._torch
        inputs = self._features(chunk, sampling_rate=sr, return_tensors="pt")
        with torch.no_grad():
            logits = self._model(inputs.input_values.to(self._device)).logits
        return ctc_decode(torch.argmax(logits, dim=-1)[0].tolist(), self._vocab)

    def analyze(self, wav_path: Path, segments: list[Segment]) -> list[WordPhonemes]:
        samples, sr = read_wav(wav_path)
        out: list[WordPhonemes] = []
        for seg in segments:
            a, b = max(0, int((seg.start - PAD) * sr)), min(len(samples), int((seg.end + PAD) * sr))
            expected = [tokenize(expected_phonemes(w.text)) for w in seg.words]
            if not any(expected) or b - a < sr * 0.08:
                continue
            observed = split_by_words(expected, tokenize(self._recognise(samples[a:b], sr)))
            for i, (w, exp, obs) in enumerate(zip(seg.words, expected, observed, strict=True)):
                if exp:
                    out.append(WordPhonemes(seg.id, i, w.text, w.start, w.end, exp, obs))
        return out
