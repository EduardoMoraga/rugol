"""Local audio transcription via faster-whisper.

Why faster-whisper
------------------
- Pure Python wrapper around CTranslate2-optimized Whisper. 4-5x faster
  than openai/whisper on CPU at the same accuracy.
- Quantized (int8) inference fits the `small` model in <300 MB RAM.
- Pip install pulls everything (no system deps like ffmpeg-bindings).

Lazy initialization
-------------------
Loading the model takes ~5-10s and 244 MB of disk for the `small`
variant (downloaded on first use). We do it on demand: the first audio
message blocks once while the model loads, every subsequent one reuses
the cached instance.

Compute fallback
----------------
On CPU we use int8 quantization. If the user has a GPU (CUDA), they can
override via `ROGOLOGO_WHISPER_DEVICE=cuda` env var.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Modelo por default. Opciones: tiny, base, small, medium, large-v3.
# `small` es el sweet spot para Spanish/English en CPU: ~3-5s por minuto
# transcribido y muy buena precisión. `tiny` es 4x más rápido pero pierde
# en español. Override con env ROGOLOGO_WHISPER_MODEL=base/medium/etc.
DEFAULT_MODEL = "small"


@lru_cache(maxsize=1)
def _get_model() -> Any:
    try:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper no está instalado. Corré: "
            "pip install faster-whisper>=1.0"
        ) from e

    model_name = os.environ.get("ROGOLOGO_WHISPER_MODEL", DEFAULT_MODEL)
    device = os.environ.get("ROGOLOGO_WHISPER_DEVICE", "cpu")
    compute_type = "int8" if device == "cpu" else "float16"
    logger.info(
        "loading faster-whisper model=%s device=%s compute=%s (first time can take 30-60s while downloading)",
        model_name, device, compute_type,
    )
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def transcribe_audio(
    audio_path: Path, language: str | None = None
) -> tuple[str, str | None]:
    """Transcribe a local audio file.

    Args:
        audio_path: path to .ogg/.mp3/.wav/etc. faster-whisper handles many formats.
        language: ISO 639-1 hint (e.g. "es", "en"). When None, auto-detected.

    Returns:
        (text, detected_language).
    """
    model = _get_model()
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,  # silence trimming → cheaper, fewer hallucinations
        beam_size=1,      # CPU-friendly. Bump to 5 for higher quality at ~2x cost.
    )
    pieces: list[str] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if text:
            pieces.append(text)
    full = " ".join(pieces).strip()
    detected = getattr(info, "language", None)
    return full, detected
