# Instalar Rogologo en una PC limpia

Guía pensada para llevar la app a otro computador sin arrastrar tus
pruebas anteriores. Funciona en Windows 10/11 (Mac/Linux similar pero
sin instalador `.bat`).

## Prerrequisitos en la PC de destino

Antes de copiar nada:

1. **Python 3.12+** ([python.org](https://www.python.org/downloads/))
2. **Node 20+** ([nodejs.org](https://nodejs.org/))
3. **pnpm**: `npm install -g pnpm`
4. **Claude CLI**: una vez instalado, ejecutar `claude /login` y autenticarse
   con tu cuenta Claude Pro/Max (o configurar `ANTHROPIC_API_KEY` después).

## Opción A — Clonar desde Git (recomendado)

```powershell
git clone <tu-fork-de-rogologo> C:\Rogologo
cd C:\Rogologo

# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r core/requirements.txt
copy .env.example .env       # editar si quieres API key en vez de subscription
uvicorn core.main:app --host 127.0.0.1 --port 8000

# Frontend (otra terminal)
cd dashboard
pnpm install
pnpm dev
```

Abrir `http://localhost:3000`. Vas a ver la pantalla de bienvenida (hero
emocional + 5 templates curados). El proyecto Workspace se crea solo,
todo lo demás está vacío.

## Opción B — Copiar carpeta + reset

Si no quieres clonar y prefieres copiar la carpeta entera desde tu PC actual:

1. Copiá la carpeta `C:\Moragent\04-LAB\rogologo` a la PC nueva
2. **EN LA PC NUEVA, antes de arrancar:**
   ```powershell
   cd C:\Rogologo
   .\.venv\Scripts\Activate.ps1   # o crea venv nuevo si Python distinto
   python scripts/reset.py --apply
   ```
   Esto borra:
   - `data/rogologo.db` y `data/scheduler.db` (toda la DB)
   - `data/settings.json` (tokens guardados, paths overrideados)
   - `agents-templates/*.md` (todos los agentes generados)
   - `skills-templates/*.md` excepto las internas de Rogologo
3. Arrancá backend + frontend como en la opción A.

## Opción C — Reset desde el dashboard (sin tocar terminal)

1. Abrí `http://localhost:3000/settings`
2. Bajá hasta **"Zona peligrosa"**
3. Click en **"Restablecer instalación"**
4. Escribe exactamente `BORRAR TODO` cuando te pregunte
5. **Reiniciá el backend manualmente** (matar uvicorn y volver a levantarlo)
   — el reset borra los archivos pero el proceso ya cargado en memoria
   sigue. Al reiniciar, init_db recrea las tablas vacías.

## Verificar que arrancó limpio

`http://localhost:8000/api/health/full` debe devolver:

```json
{
  "schema": {
    "projects_total": 1,
    "projects_named": 0,
    "agents": 0,
    "schedules": 0
  },
  "first_use": true
}
```

`first_use: true` activa el OnboardingHero en `/projects` con los 5
templates listos para clonar.

## Llevarte tus tokens (sin la data)

Si en tu PC actual configuraste tokens de Telegram/Slack y quieres usarlos
en la PC nueva sin recrearlos:

1. Antes del reset, copiá `data/settings.json` aparte
2. Después del reset y de arrancar limpio, pega ese archivo de vuelta en
   `data/settings.json` y reiniciá el backend
3. Los tokens vuelven, las DB queda vacía

## Troubleshooting

- **El dashboard muestra "first_use" pero no aparece el hero**: hard-refresh
  con Ctrl+Shift+R (puede haber cache de la versión anterior).
- **Crear proyecto falla con "slug ya existe"**: significa que el reset no
  corrió. Verifica con `python scripts/reset.py --dry-run` qué hay.
- **Telegram/Slack adapters no arrancan**: el backend ya no es fatal en eso
  desde Capa 14 — sigue funcionando sin chat ops. Mira los logs (`uvicorn`
  stderr) para el motivo del timeout/error. Casi siempre es token inválido
  o red bloqueada.
