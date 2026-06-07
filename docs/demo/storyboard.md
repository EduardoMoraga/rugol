# Rugol v0.8.0 — Storyboard del video de lanzamiento

**Duración objetivo:** 90–120 s. **Tono:** sobrio, técnico, sin hype.
**Voz:** Eduardo Moraga, primera persona, español neutro.

## Antes de grabar (setup)
- Terminal grande, fuente ~18 pt, tema oscuro, ventana limpia (sin tabs).
- `rugol up` corriendo (verificá con `rugol status`).
- Teléfono con los 2 bots de Telegram a mano.
- Navegador con `localhost:3000` abierto en una pestaña.
- (Opcional) Obsidian instalado y la carpeta `~/.rugol/app/agent-memory` abierta como vault, en Graph view.
- Grabá a 1080p mínimo. En Mac: Cmd+Shift+5.

---

## Plano por plano

### Shot 1 — Hook (0:00–0:08) · cámara o slide de texto
**En pantalla:** tu cara o un fondo negro con una frase.
**Voz en off:**
> "Soy economista, no programador. Y construí mi propio sistema de agentes de IA. Se llama Rugol."

### Shot 2 — Terminal: el demo auto-reproducible (0:08–0:55)
**Acción:** corré `bash scripts/demo.sh` y dejá que avance solo. Grabá la terminal.
Cubre, narrado por el propio script: versión/estado → un bot por proyecto → la memoria como cerebro navegable → plantillas (Sesgo Útil) → self-improving.
**Voz en off (encima, opcional, reforzando):**
> "Todo corre en mi máquina. Sin nube. Cada proyecto tiene su propio bot de Telegram, su propio agente, su propia memoria."

> "Y esa memoria no es una lista: es un grafo. Lo que mis agentes aprenden se enlaza solo."

### Shot 3 — Teléfono: dos bots, dos personalidades (0:55–1:12)
**Acción:** grabá el teléfono (o screen mirroring). Escribí al bot "Personal" algo cotidiano; al bot "Analista" un set de números de ventas. Mostrá las dos respuestas distintas, en paralelo.
**Voz en off:**
> "Dos contactos distintos. Uno me organiza el día; el otro analiza datos. No se cruzan."

### Shot 4 — Navegador: clonar un equipo (1:12–1:30)
**Acción:** en `localhost:3000`, entrá al catálogo de plantillas, mostrá la card "Sesgo Útil", clic en clonar. Mostrá los 5 agentes desplegados.
**Voz en off:**
> "¿Un equipo nuevo? Un click. Esto es Sesgo Útil: cinco agentes que convierten papers de economía conductual en columnas publicables."

### Shot 5 — El agente se mejora a sí mismo (1:30–1:45)
**Acción:** terminal `rugol evolve assistant` (o mostrá la pestaña Evolution en el dashboard con propuestas). Mostrá aceptar/rechazar.
**Voz en off:**
> "Y los agentes proponen mejoras a su propio prompt. Yo apruebo o rechazo. La máquina sugiere; la decisión es mía."

### Shot 6 — Cierre / CTA (1:45–2:00)
**En pantalla:** la línea de instalación + el repo.
**Voz en off:**
> "Open source. Una línea para instalarlo. Si te sirve, decime para qué lo usaste — eso mueve el roadmap."
**Texto en pantalla:**
```
github.com/EduardoMoraga/rugol
curl -fsSL https://raw.githubusercontent.com/EduardoMoraga/rugol/main/installer/install.sh | bash
```

---

## Notas de edición
- Música: mínima, instrumental, baja. Nada épico.
- Subtítulos quemados (mucha gente mira sin audio en LinkedIn).
- Cortá los tiempos muertos del `evolve` (los ~30 s de espera) con un corte seco.
- Si grabás el demo y querés acelerarlo: `DEMO_SPEED=0.6 bash scripts/demo.sh`.
- Versión corta para reel (≤30 s): solo Shot 1 + Shot 3 (bots) + Shot 6.
