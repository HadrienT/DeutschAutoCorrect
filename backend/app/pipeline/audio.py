"""Audio helpers: ffmpeg normalisation, duration, waveform peaks."""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000


class AudioError(RuntimeError):
    pass


def normalize_to_wav(src: Path, dst: Path) -> Path:
    """Convert any audio/video container to mono 16 kHz PCM WAV."""
    if shutil.which("ffmpeg") is None:
        raise AudioError("ffmpeg est introuvable : installez-le pour traiter les fichiers audio.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
           "-c:a", "pcm_s16le", str(dst)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not dst.exists():
        raise AudioError(f"Fichier audio illisible : {proc.stderr.strip()[:300]}")
    return dst


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Return float32 mono samples in [-1, 1] and the sample rate."""
    with wave.open(str(path), "rb") as w:
        sr, n, width, ch = w.getframerate(), w.getnframes(), w.getsampwidth(), w.getnchannels()
        raw = w.readframes(n)
    if width != 2:
        raise AudioError("WAV 16 bits attendu")
    data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data, sr


def duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def compute_peaks(samples: np.ndarray, n_bins: int = 800) -> list[float]:
    """Max-abs amplitude per bin, normalised to [0, 1]."""
    if samples.size == 0:
        return [0.0] * n_bins
    n_bins = max(1, min(n_bins, samples.size))
    edges = np.linspace(0, samples.size, n_bins + 1, dtype=int)
    peaks = np.array([np.abs(samples[a:b]).max() if b > a else 0.0
                      for a, b in zip(edges[:-1], edges[1:], strict=True)])
    m = peaks.max()
    if m > 0:
        peaks = peaks / m
    return [round(float(p), 3) for p in peaks]


def write_wav(path: Path, samples: np.ndarray, sr: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
