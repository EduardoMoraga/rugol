# Troubleshooting

Rugol corre nativo: dos procesos (core en :8000, dashboard en :3000) bajo
`~/.rugol`. Empezá siempre por acá:

```
rugol status     # ¿están arriba los procesos y responden los puertos?
rugol doctor     # runtimes, config y la cuenta de Claude verificada de verdad
rugol logs core  # el error concreto
```

## El dashboard funciona pero el agente no responde

El síntoma clásico: la UI carga perfecto y cada run falla. Tiene sentido — el
core y el dashboard no necesitan credenciales para servir páginas; las
credenciales sólo se usan cuando un run invoca el CLI de Claude.

```
rugol auth --verify
```

Eso hace una llamada real al API. Si dice que la credencial fue rechazada:

```
rugol login
```

Detalles importantes:

- **El binario que importa no es el `claude` de tu PATH.** Rugol corre el CLI
  que viene dentro de `claude-agent-sdk`. Pueden ser versiones distintas con
  credenciales distintas. `rugol auth` te dice cuál está usando.
- **`rugol auth` sin `--verify` es barato pero no prueba nada.**
  `claude auth status` reporta lo que está *configurado*: un token revocado
  aparece como conectado. La única respuesta honesta es la llamada real.
- **Dos credenciales configuradas a la vez** (token en el `.env` **y** login en
  la máquina) funciona, pero vuelve ambiguo el diagnóstico. `rugol login` deja
  una sola.

## "Se desconectó el bot" en el chat

Antes el chat mostraba sólo `failed` y el motivo quedaba en `/runs/<id>`, así
que un fallo de credenciales se leía igual que uno de red. Ahora el mensaje
aparece en el propio chat, y si huele a auth, sugiere `rugol login`.

Si querés el detalle completo de una corrida: `/runs/<id>` en el dashboard, o

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/runs?limit=5" | Format-List
```

## No hay comando para reconectar la cuenta

Sí lo hay, desde v0.7.2:

```
rugol login              # login interactivo (navegador)
rugol login --token      # token largo, para un server headless
rugol login --api-key    # API key de Anthropic
rugol auth [--verify]    # estado
rugol logout
```

Antes el único camino era `rugol setup`, que reescribe el `.env` entero. Ya no
hace falta: `rugol login` toca sólo las claves de auth.

## Telegram: "Conflict: terminated by other getUpdates request"

Hay otro poller con el mismo token. Causas típicas: un proceso viejo que quedó
colgado, o el mismo bot corriendo en otra máquina.

```powershell
rugol down
Get-Process python -ErrorAction SilentlyContinue
rugol up
```

Un token no puede estar en dos lados. Si querés dos bots, `rugol bot add` con
tokens distintos (uno por proyecto).

## El dashboard sale sin estilos o en blanco

Casi siempre es un build a medias. En Windows el server de Next bloquea
archivos de `.next`, así que hay que bajarlo antes de compilar:

```
rugol down
rugol build
rugol up
```

Si sigue en blanco, abrí la consola del navegador y mirá `rugol logs dashboard`.

## Un puerto está ocupado

```powershell
# Windows
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess
# Mac / Linux
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

Para mover los puertos, editá `CORE_PORT` / `DASHBOARD_PORT` en `~/.rugol/.env`
y `rugol restart`.

## Cambié el `.env` y no pasó nada

El `.env` se lee **al arrancar**. `rugol restart`.

## Edité un agente `.md` y el dashboard no lo muestra

El watcher hace debounce de 200 ms y el dashboard poolea cada 5 s. Esperá 10
segundos. Si sigue trabado, `rugol restart` y revisá que el frontmatter tenga
`name` y `model` válidos (`rugol logs core` lo dice).

## Mi suscripción me está limitando

`MAX_CONCURRENT_RUNS=1` en `~/.rugol/.env` y `rugol restart`. Si necesitás más
concurrencia, pasá a API key: `rugol login --api-key`.

## No lo alcanzo desde otro equipo

Es lo esperado: core y dashboard están atados a `127.0.0.1`. Ver
[remote-access.md](remote-access.md).

## Reinstalé y perdí los schedules

Pasaba en versiones anteriores a v0.7.2: `settings.json` y `scheduler.db` vivían
dentro de `~/.rugol/app/data`, y reinstalar borra el app dir. Ahora viven en
`~/.rugol/data` y el core adopta automáticamente lo que quedó en la ubicación
vieja (lo registra en `rugol logs core`). Si tenías un backup de
`app/data/settings.json`, copialo a `~/.rugol/data/settings.json` y reiniciá.

## Empezar de cero

```
rugol uninstall          # pregunta antes de borrar ~/.rugol
```

O `/settings` → **Zona peligrosa** → *Restablecer instalación*, y después
`rugol restart`.
