# rogologo-frontend — memoria

## Aprendizajes del scaffolding inicial (2026-05-02)

- Next.js 15 con App Router → `output: "standalone"` para Docker (genera `server.js`).
- Tailwind v4 usa `@import "tailwindcss"` en globals.css y `@tailwindcss/postcss` plugin (no más `tailwind.config.ts` obligatorio).
- `@pixi/react` v8 expone componentes via `extend({ Container, Graphics, Text })` y entonces se usan como `pixiContainer`, `pixiGraphics`, `pixiText`.
- `react-query` con `refetchInterval: 5000` para overview cards — balance entre frescura y costo.
- SSE en cliente: `EventSource` con backoff exponencial; reconnect cap 15s.
- `dynamic(() => import(...), { ssr: false })` para el canvas Pixi (no funciona en SSR).

## Decisiones de diseño confirmadas

- Paleta zinc/slate dark + verde lima `#84cc16` como acento de "running".
- Geist Sans + Geist Mono (default Next.js).
- Sin emojis en UI. Iconos `lucide-react`.
- Cards con `border-color: --color-border` y hover sutil.
- Empty states siempre, con CTA claro.

## Pendientes técnicos (Sprint 2)

- [ ] i18n con `next-intl` — hoy todo está en EN hardcoded.
- [ ] Shadcn/ui setup completo via `pnpm dlx shadcn@latest init`.
- [ ] Cron picker visual para crear schedules (hoy es un input crudo).
- [ ] Tooltip y click handlers en sprites del ant-farm.
- [ ] `react-flow` graph viewer real para `/ontology` (hoy es lista plana).
- [ ] Diff viewer con sintaxis para `/improvements` (hoy es `<pre>`).
- [ ] Sound effects opt-in para el ant-farm.
