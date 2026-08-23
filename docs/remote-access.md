# Acceso remoto (Tailscale)

Rugol ata el core y el dashboard a `127.0.0.1`, a propósito: **el API no tiene
capa de autenticación**, y los agentes tienen shell y filesystem. Cualquiera que
alcance el puerto puede correr un agente en tu máquina. Ver la sección
*Security model* del README.

Así que la respuesta a "quiero verlo desde el celular" no es cambiar el bind:
es un túnel. Tailscale es el camino más corto y no requiere abrir nada en el
firewall ni tocar el código.

## Por qué alcanza con un solo puerto

El dashboard hace de proxy: Next reescribe `/api/*` hacia el core **desde el
servidor**. El navegador nunca habla con el puerto 8000. Exponés 3000 y listo —
el core sigue siendo inalcanzable desde afuera.

## Recetas

En la máquina donde corre Rugol, con Tailscale ya instalado y logueado:

```powershell
# HTTP dentro del tailnet (no necesita certificados)
tailscale serve --bg --http=80 3000
tailscale serve status
```

Queda accesible desde cualquier dispositivo del tailnet en
`http://<nombre-de-la-máquina>.<tu-tailnet>.ts.net/`.

Si activás **HTTPS Certificates** en la consola de Tailscale (Settings → DNS),
la versión con TLS es igual de simple:

```powershell
tailscale serve --bg 3000
```

Para dar de baja la exposición:

```powershell
tailscale serve reset
```

## Verificar desde otro equipo

```bash
tailscale status                                  # ¿está online la máquina?
curl -s http://<host>.<tailnet>.ts.net/api/health # debe responder {"status":"ok"}
```

Si el host responde al ping pero el puerto 3000 da *connection refused*, eso es
lo esperado sin `tailscale serve`: el servicio está atado a `127.0.0.1`. No es
un síntoma de que Rugol esté caído — comprobalo con `rugol status` en la propia
máquina.

## Lo que NO conviene hacer

- **Cambiar el bind a `0.0.0.0`.** Deja el control plane abierto a toda la red
  local, sin credencial. Si igual lo hacés, poné un reverse proxy con auth
  adelante y limitá el firewall a la interfaz de Tailscale.
- **Publicar los puertos con `tailscale funnel`.** Funnel expone a la Internet
  pública. Un API sin auth con acceso a shell no puede vivir ahí.
- **Reenviar el 8000.** No hace falta: el dashboard ya proxea el API.

## Alternativas equivalentes

- **RDP / VNC**: operás la máquina, no el servicio. Es lo más cerrado y no
  requiere exponer nada.
- **Túnel SSH**: `ssh -L 3000:127.0.0.1:3000 usuario@host`, y abrís
  `http://localhost:3000` en tu equipo.
