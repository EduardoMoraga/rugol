# Troubleshooting

Rugol corre nativo: dos procesos (core en :8000, dashboard en :3000) bajo
`~/.rugol`. Empezá siempre por acá:

```
rugol status     # ¿están arriba los procesos y responden los puertos?
rugol doctor     # runtimes, config y la cuenta de Claude verificada de verdad
rugol logs core  # el error concreto
```

## `rugol update` dice "codigo actualizado" pero nada cambia

Síntoma exacto: en el medio del output aparece `Please commit your changes or
stash them before you merge. Aborting`, y dos líneas después
`[OK] codigo actualizado`. La versión del dashboard que compila sigue siendo la
vieja.

Es un círculo cerrado, no un error tuyo. Hasta junio de 2026 el launcher usaba
`git pull`, que aborta si el runtime dejó archivos modificados en el
directorio de la app. Y el launcher sólo se refresca *después* de un fetch
exitoso — así que nunca podía arreglarse a sí mismo.

Una línea lo rompe:

```powershell
irm https://raw.githubusercontent.com/EduardoMoraga/rugol/main/scripts/repair.ps1 | iex
```

Guarda los cambios locales en un `git stash` (recuperables con
`git -C "$HOME\.rugol\app" stash pop`), pone el código al día, refresca el
launcher, reinstala dependencias, recompila y levanta. Tus datos no se tocan.
De ahí en adelante `rugol update` funciona solo: la versión nueva hace
`reset --hard` y sólo dice "codigo actualizado" si el fetch realmente anduvo.

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

El puerto del core queda **horneado en el build del dashboard** (Next.js
serializa el destino del proxy al compilar), así que mover `CORE_PORT` obliga a
recompilar. `rugol up` y `rugol restart` lo detectan solos y recompilan: vas a
ver *"el dashboard fue compilado contra el puerto X y el core ahora usa Y"* y
un build de 1-2 minutos. No hace falta que corras `rugol build` a mano.

## `rugol up` dice "core saludable" pero el dashboard está roto

No debería pasar más: `up` sólo canta verde si el que contesta en el puerto es
el core de Rugol —lo comprueba por la marca que devuelve `/api/health`—, y se
detiene si el puerto lo tiene otro programa. Si ves *"el puerto N lo tiene otro
programa"*, cerralo o cambiá `CORE_PORT` como se explica arriba.

`rugol status` distingue los tres casos: el core responde, el puerto responde
pero **no es Rugol**, o no responde nadie.

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
