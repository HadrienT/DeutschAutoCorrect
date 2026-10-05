"""German grapheme-to-phoneme via the espeak-ng binary (optional)."""
from __future__ import annotations

import re
import shutil
import subprocess
from functools import lru_cache


def espeak_available() -> bool:
    return shutil.which("espeak-ng") is not None or shutil.which("espeak") is not None


@lru_cache(maxsize=8192)
def expected_phonemes(word: str) -> str:
    clean = re.sub(r"[^\wäöüÄÖÜß'-]", "", word)
    if not clean:
        return ""
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("espeak-ng est requis pour la prononciation (apt install espeak-ng)")
    out = subprocess.run([exe, "-q", "--ipa", "-v", "de", clean], capture_output=True, text=True,
                         timeout=10)
    return re.sub(r"\s+", "", out.stdout.strip())
