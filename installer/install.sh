#!/usr/bin/env bash
# rugol installer (Mac/Linux) — native, no Docker.
#   curl -fsSL https://raw.githubusercontent.com/EduardoMoraga/rugol/main/installer/install.sh | bash
#
# Provisions its OWN runtimes (Python via uv, Node pinned) so you don't need
# anything preinstalled. State lives in ~/.rugol.
#
# Env overrides: RUGOL_HOME, RUGOL_SRC (install from a local dir), RUGOL_REPO, RUGOL_REF
set -euo pipefail

RUGOL_HOME="${RUGOL_HOME:-$HOME/.rugol}"
APP_DIR="$RUGOL_HOME/app"
RT="$RUGOL_HOME/runtime"
REPO="${RUGOL_REPO:-https://github.com/EduardoMoraga/rugol.git}"
REF="${RUGOL_REF:-main}"
BIN_DIR="$HOME/.local/bin"
NODE_VER="v20.18.1"

G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; B=$'\033[1m'; X=$'\033[0m'
ok()   { echo "  ${G}✓${X} $*"; }
warn() { echo "  ${Y}!${X} $*"; }
die()  { echo "  ${R}✗${X} $*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

echo ""
echo "${B}Instalando rugol${X} → $RUGOL_HOME  ${B}(sin Docker)${X}"
echo ""

# ── 1) Traer el código ───────────────────────────────────────────────────────
mkdir -p "$RUGOL_HOME"
if [ -n "${RUGOL_SRC:-}" ]; then
  [ -d "$RUGOL_SRC" ] || die "RUGOL_SRC no es un directorio: $RUGOL_SRC"
  rm -rf "$APP_DIR"; mkdir -p "$APP_DIR"
  if have rsync; then
    rsync -a --exclude '.git' --exclude 'node_modules' --exclude '.next' \
          --exclude '.venv' --exclude 'data' --exclude 'logs' "$RUGOL_SRC"/ "$APP_DIR"/
  else cp -R "$RUGOL_SRC"/. "$APP_DIR"/; fi
  ok "código copiado desde $RUGOL_SRC"
else
  have git || die "git no está instalado."
  if [ -d "$APP_DIR/.git" ]; then git -C "$APP_DIR" pull --ff-only && ok "código actualizado"
  else rm -rf "$APP_DIR"; git clone --depth 1 --branch "$REF" "$REPO" "$APP_DIR" && ok "código clonado ($REF)"; fi
fi

mkdir -p "$RUGOL_HOME"/{data,logs,agents,skills,run} "$RT"

# ── 2) Python aislado (vía uv — descarga su propio Python 3.12) ───────────────
if ! have uv; then
  echo "  instalando uv (gestor de Python)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || die "no pude instalar uv"
fi
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
have uv || die "uv no quedó en PATH"
ok "uv: $(uv --version 2>/dev/null)"

echo "  creando entorno Python aislado + dependencias del backend..."
uv venv "$RT/venv" --python 3.12 >/dev/null 2>&1 || die "uv venv falló"
uv pip install --python "$RT/venv/bin/python" -q -r "$APP_DIR/core/requirements.txt" || die "falló la instalación de deps"
ok "backend listo ($("$RT/venv/bin/python" --version 2>&1))"

# ── 3) Node (sistema si ≥18, si no lo bajamos pinneado) ───────────────────────
need_node=1
if have node; then
  maj="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  [ "$maj" -ge 18 ] && { need_node=0; ok "node del sistema: $(node --version)"; }
fi
if [ "$need_node" -eq 1 ]; then
  case "$(uname -s)" in Darwin) NOS=darwin; EXT=tar.gz;; Linux) NOS=linux; EXT=tar.xz;; *) die "OS sin soporte de node bundle";; esac
  case "$(uname -m)" in arm64|aarch64) NARCH=arm64;; x86_64|amd64) NARCH=x64;; *) die "arch sin soporte";; esac
  URL="https://nodejs.org/dist/${NODE_VER}/node-${NODE_VER}-${NOS}-${NARCH}.${EXT}"
  echo "  bajando Node ${NODE_VER} (${NOS}-${NARCH})..."
  mkdir -p "$RT/node"
  if [ "$EXT" = "tar.gz" ]; then curl -fsSL "$URL" | tar -xz -C "$RT/node" --strip-components=1
  else curl -fsSL "$URL" | tar -xJ -C "$RT/node" --strip-components=1; fi
  export PATH="$RT/node/bin:$PATH"
  corepack enable pnpm >/dev/null 2>&1 || true
  ok "node embebido en $RT/node"
fi

# ── 4) Instalar el launcher en el PATH ───────────────────────────────────────
mkdir -p "$BIN_DIR"
install -m 0755 "$APP_DIR/cli/rugol" "$BIN_DIR/rugol"
ok "launcher instalado en $BIN_DIR/rugol"

# ── 5) Compilar el dashboard ─────────────────────────────────────────────────
echo "  compilando el dashboard..."
RUGOL_HOME="$RUGOL_HOME" RUGOL_APP_DIR="$APP_DIR" "$BIN_DIR/rugol" build >/dev/null 2>&1 \
  && ok "dashboard compilado" || warn "el dashboard no compiló — corré 'rugol build' para ver el detalle"

case ":$PATH:" in
  *":$BIN_DIR:"*) : ;;
  *) warn "$BIN_DIR no está en tu PATH — agregá:  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

echo ""
echo "${G}${B}Listo — sin Docker.${X}  Próximos pasos:"
echo ""
echo "   ${B}rugol setup${X}    # auth + modelo + Telegram"
echo "   ${B}rugol up${X}       # levanta todo y abre el dashboard"
echo ""
