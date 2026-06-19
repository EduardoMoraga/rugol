"""Integración de entrevistas de voz "Sofía" (ElevenLabs) dentro de Rugol.

Trae las conversaciones reales del agente conversacional de ElevenLabs, las
puntúa contra el instrumento BARS v1 (mismo método que el resto de Rugol:
claude-agent-sdk sobre la suscripción Claude, con fallback a `claude -p`), y
deja cada candidato evaluado en el pipeline de candidatos (kind="candidate").

Origen conceptual: HRO2/voice-interviewer (scorer + instrumento + orquestador).
Aquí queda autogestionado dentro del backend FastAPI.
"""
from core.voice.sync import sync_interviews

__all__ = ["sync_interviews"]
