# rogologo-devops — memoria

## Aprendizajes del scaffolding inicial (2026-05-02)

- Docker Compose v2 sintaxis: `services.<n>.healthcheck.test` con array, `condition: service_healthy` en `depends_on`.
- Dockerfile core necesita Node 20 además de Python (porque bundlea `claude` CLI).
- Imagen core final: ~400-500 MB (python:3.12-slim + node + claude-agent-sdk). Aceptable.
- Imagen dashboard: multi-stage con `output: "standalone"` → ~150 MB.
- PowerShell 5.1 default en Windows 10/11 — no asumir 7. `Read-Host -AsSecureString` para tokens.
- `.bat` wrapper → llama `powershell -NoProfile -ExecutionPolicy Bypass -File`.
- `Invoke-WebRequest -UseBasicParsing` para healthcheck poll desde el wizard.

## Decisiones tomadas

- Dos profiles: default (SQLite, sin Redis) y prod (Postgres + Redis vía overlay).
- `docker-compose.prod.yml` se aplica con `-f` adicional, no reemplaza el default.
- Healthcheck en core → dashboard espera `service_healthy` antes de arrancar.
- GitHub Actions: 2 workflows (`ci.yml` para PRs, `release.yml` para tags `v*.*.*`).
- Imagenes a `ghcr.io/<owner>/rogologo-{core,dashboard}` — no Docker Hub (mejor integrado con repos GH).

## Pendientes técnicos (Sprint 3)

- [ ] Probar wizard end-to-end en una VM Windows limpia.
- [ ] Compilar `.exe` único con [pyinstaller](https://pyinstaller.org) o [Inno Setup](https://jrsoftware.org/isinfo.php) que envuelva install.bat.
- [ ] Codesigning del .exe (requiere cert).
- [ ] Trivy scan de imágenes en CI (security gate).
- [ ] Backup automático con cron container.
- [ ] Watchtower opcional para auto-update.
- [ ] Tailscale/Cloudflare Tunnel docs para acceso remoto.
