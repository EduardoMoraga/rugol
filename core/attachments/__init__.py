"""Attachments — extract text from Office docs, transcribe audio with Whisper.

Used by adapters (Telegram, Slack future) to handle non-text inputs.
"""
from core.attachments.extractor import extract_text, FILE_KIND, classify_path
from core.attachments.transcriber import transcribe_audio

__all__ = ["extract_text", "transcribe_audio", "FILE_KIND", "classify_path"]
