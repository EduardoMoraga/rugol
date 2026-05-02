# rogologo-architect — memoria

> Arquitecto principal de Rogologo. Decisiones, mitigaciones, preferencias.

## Decisiones tomadas (2026-05-02)

- **Stack final**: Python FastAPI + Next.js 15 + Tailwind v4 + react-pixi + Docker Compose. Ver ADR-001.
- **LLM auth dual**: subscription default + API opt-in via `USE_SUBSCRIPTION` flag. Ver ADR-002.
- **Visualización**: ant-farm 2D con `@pixi/react`, hex grid auto-laid, fallback cards-only > 100 sprites. Ver ADR-003.
- **Ontología**: SQLite triple store, escritura via tool tipado, no auto-merge. Ver ADR-004.
- **Self-improving**: reflection loop con human-in-the-loop obligatorio, cap 1 reflexión/agente/día. Ver ADR-004.
- **Distribución**: Docker Compose + installer Windows .bat → wizard PowerShell. No bundles nativos.

## Preferencias confirmadas con Edu

- Quiere algo robusto y promocionable a Anthropic — no proyecto de fin de semana.
- Open source desde día 1 con LICENSE MIT.
- Quiere ver a los agentes "trabajar" visualmente — origen de la decisión ant-farm.
- API paga es ok si hace falta para concurrencia. No es restricción la suscripción.
- "Rogologo" nombre confirmado (origen onomatopéyico de su hija).
- Bilingüe ES/EN paritario.

## Riesgos vivos

- **Rate limits de subscription**: scheduler debe escalonar. `MAX_CONCURRENT_RUNS=3` default.
- **Drift de ontología**: agentes podrían escribir facts contradictorios. Mitigación = `maintenance` agent semanal + predicate vocabulary.
- **Self-improving runaway**: si no se respeta el cap diario, puede consumir tokens innecesariamente. Trigger sólo si 3 fails seguidos o cada 10 runs sin propuesta abierta.
- **Docker Desktop en Windows**: fricción de instalación grande para usuarios no técnicos. Mitigado por wizard que detecta y guía.

## Reglas que aprendí del proyecto

- Reusar `eduagent-gateway/gateway.py` para Telegram (single-instance lock, descarga adjuntos, audio transcription, `_sdk_env()`).
- No reescribir mission-control de OpenClaw — Rogologo es producto distinto, build from scratch para no contaminar IP.
- Ant-farm es la cara distintiva del producto. Sin él se ve como otro dashboard más.
