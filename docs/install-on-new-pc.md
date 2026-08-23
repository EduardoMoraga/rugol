# Instalar Rugol en una PC nueva

Una línea instala todo. Rugol trae su propio Python (vía [uv](https://github.com/astral-sh/uv))
y su propio Node, así que en la máquina destino sólo hace falta **git**
(en Windows, [Git for Windows](https://git-scm.com/download/win)).

**No hace falta instalar Claude Code.** El backend trae el CLI de Claude
adentro del paquete `claude-agent-sdk`, y ése es el que corre tus agentes —
no el `claude` que tengas en el PATH. Por eso el login se hace con
`rugol login` y no con `claude login`.

## Instalar

**Windows** (PowerShell)
```powershell
iwr -useb https://raw.githubusercontent.com/EduardoMoraga/rugol/main/installer/install.ps1 | iex
```

**Mac / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/EduardoMoraga/rugol/main/installer/install.sh | bash
```

Después, desde cualquier terminal:

```
rugol setup     # modelo, Telegram opcional, agente por defecto
rugol login     # conecta tu cuenta de Claude
rugol up        # levanta core + dashboard y abre el navegador
```

`rugol setup` pregunta por la autenticación, pero podés dejar el token vacío
y resolverlo con `rugol login`, que es el camino recomendado en un escritorio.

## Conectar la cuenta de Claude

`rugol login` abre el flujo de Anthropic en el navegador y guarda la
credencial en el sistema (`%USERPROFILE%\.claude` / `~/.claude`).

En un servidor sin sesión interactiva, usá un token largo:

```
rugol login --token      # corre `claude setup-token` y lo guarda en el .env
rugol login --api-key    # o una API key de Anthropic (billing aislado)
```

Cualquiera de las tres formas termina con una **verificación real**: una
llamada mínima al API que confirma que la credencial funciona. Después:

```
rugol auth              # qué credencial está configurada (rápido)
rugol auth --verify     # ¿funciona de verdad? (llamada real al API)
rugol logout            # desconecta y limpia credenciales del .env
```

`rugol login` sólo toca las claves de auth del `.env`: no te vuelve a
preguntar modelo, token de Telegram ni agente por defecto.

## Dónde vive tu estado

Todo bajo `~/.rugol` (`%USERPROFILE%\.rugol` en Windows):

```
~/.rugol/
├── app/       el código (reinstalar lo reemplaza entero)
├── data/      DB, jobstore del scheduler, settings.json, adjuntos
├── agents/    tus agentes .md
├── skills/    tus skills .md
├── logs/      core.log, dashboard.log
└── .env       tu configuración
```

La separación importa: `app/` es reemplazable, todo lo demás no.
`rugol update` y una reinstalación desde cero dejan `data/`, `agents/`,
`skills/` y `.env` intactos.

> Versiones anteriores a v0.7.2 guardaban `settings.json` y `scheduler.db`
> dentro de `app/data/`, así que una reinstalación se llevaba los schedules y
> los tokens guardados desde el dashboard. Al arrancar, el core los adopta
> automáticamente desde la ubicación vieja (copia, no mueve) y lo registra en
> el log. No hay que hacer nada a mano.

## Verificar que quedó bien

```
rugol status     # core y dashboard arriba, puertos respondiendo
rugol doctor     # runtimes, puertos, config Y la cuenta de Claude verificada
                 # contra el API (hace una llamada real, ~2s)
```

Y una corrida real, sin pasar por la UI:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/agents" | Select-Object id, name, status

$r = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/agents/1/run" `
  -ContentType "application/json" `
  -Body (@{ prompt = "Respondé solamente: OK" } | ConvertTo-Json)

Start-Sleep 25
Invoke-RestMethod "http://127.0.0.1:8000/api/runs/$($r.run_id)" | Format-List
```

Si el run queda en `failed`, el campo `error_message` dice por qué. El mismo
mensaje aparece ahora en el chat del dashboard y en `/runs/<id>`.

## Que arranque solo

```
rugol autostart on      # tarea al iniciar sesión + watchdog cada 5 min
rugol autostart status
```

En Windows el disparador es **al iniciar sesión**: si reiniciás la máquina y
nadie entra (ni por RDP), Rugol no levanta. Tenelo en cuenta si dependés de un
schedule de la mañana.

## Empezar de cero en la máquina nueva

Si querés la instalación limpia, sin tus pruebas anteriores:

```
rugol uninstall     # pregunta antes de borrar ~/.rugol
```

O desde el dashboard, `/settings` → **Zona peligrosa** → *Restablecer
instalación* (pide escribir `BORRAR TODO`). Después reiniciá el backend con
`rugol restart` para que se recreen las tablas vacías.

## Llevarte tus tokens sin la data

1. Copiá `~/.rugol/data/settings.json` de la máquina vieja.
2. En la nueva, después de instalar y antes de `rugol up`, pegalo en
   `~/.rugol/data/settings.json`.
3. `rugol up`. Vuelven los tokens de Telegram/Slack y las rutas; la DB queda
   vacía.

Las credenciales de Claude **no** están ahí: van por `rugol login` en cada
máquina (o por el token del `.env`, que sí es portable).

## Acceso remoto

Ver [remote-access.md](remote-access.md). Resumen: no cambies el bind, tunelealo
con Tailscale.
