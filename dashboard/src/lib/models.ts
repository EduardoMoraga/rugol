// Los modelos que el dashboard OFRECE. Espejo de `core/llm_models.py`
// (MODEL_CHOICES) — si cambiás uno, cambiá el otro. El backend acepta además
// los IDs de generaciones anteriores (LEGACY_MODELS allá), así que un agente
// viejo sigue guardándose: para eso está `withCurrent` acá abajo.

export interface ModelChoice {
  value: string;
  label: string;
}

export const MODEL_CHOICES: ModelChoice[] = [
  { value: "claude-sonnet-5", label: "Sonnet 5 — equilibrado (recomendado)" },
  { value: "claude-opus-5", label: "Opus 5 — razonamiento profundo" },
  { value: "claude-haiku-4-5", label: "Haiku 4.5 — rápido y barato" },
];

export const DEFAULT_MODEL = "claude-sonnet-5";

/** Agrega el modelo actual del agente si es de una generación anterior, para
 *  que editar otro campo no le cambie el modelo por debajo. */
export function withCurrent(current?: string | null): ModelChoice[] {
  if (!current || MODEL_CHOICES.some((m) => m.value === current)) return MODEL_CHOICES;
  return [...MODEL_CHOICES, { value: current, label: `${current} — actual` }];
}
