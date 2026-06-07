#!/usr/bin/env bash
# Rugol — demo auto-reproducible para grabar en video.
#
#   1. Abrí una terminal grande, fuente ~18pt, tema oscuro.
#   2. Grabá la pantalla (Mac: Cmd+Shift+5 → grabar porción/pantalla).
#   3. Corré:  bash scripts/demo.sh
#   4. El script narra y ejecuta solo. Vos solo grabás.
#
# Es read-mostly y repetible. La parte de self-improving (rugol evolve) usa
# Opus y tarda ~30s; se salta con  DEMO_FAST=1 bash scripts/demo.sh
#
# Ritmo: ajustable con DEMO_SPEED (0.5 = lento, 2 = rápido). Default 1.
set -uo pipefail

SPEED="${DEMO_SPEED:-1}"
FAST="${DEMO_FAST:-0}"
CORE="http://127.0.0.1:8000"
DASH="http://127.0.0.1:3000"
RUGOL_HOME="${RUGOL_HOME:-$HOME/.rugol}"
PY="$RUGOL_HOME/runtime/venv/bin/python"
[ -x "$PY" ] || PY="python3"

B=$'\033[1m'; D=$'\033[2m'; X=$'\033[0m'
G=$'\033[38;5;42m'; C=$'\033[38;5;45m'; Y=$'\033[38;5;220m'; P=$'\033[38;5;141m'; GR=$'\033[38;5;245m'

_sleep() { sleep "$(echo "$1 * $SPEED" | bc -l 2>/dev/null || echo "$1")"; }

# Typewriter para la narración.
say() {
  local txt="$1" color="${2:-$X}"
  printf "%s" "$color"
  local i ch
  for (( i=0; i<${#txt}; i++ )); do
    ch="${txt:$i:1}"; printf "%s" "$ch"; sleep "$(echo "0.012 * $SPEED" | bc -l 2>/dev/null || echo 0.012)"
  done
  printf "%s\n" "$X"
}

# Tarjeta de sección.
card() {
  local title="$1"
  echo ""; echo ""
  printf "${C}${B}  ┌%s┐${X}\n" "$(printf '─%.0s' $(seq 1 56))"
  printf "${C}${B}  │${X}${B}  %-52s${X}${C}${B}│${X}\n" "$title"
  printf "${C}${B}  └%s┘${X}\n" "$(printf '─%.0s' $(seq 1 56))"
  echo ""
}

# Mostrar y ejecutar un comando (con prompt simulado y tipeo).
run() {
  local cmd="$1"
  printf "${GR}❯${X} "
  local i
  for (( i=0; i<${#cmd}; i++ )); do printf "%s" "${cmd:$i:1}"; sleep "$(echo "0.02 * $SPEED" | bc -l 2>/dev/null || echo 0.02)"; done
  printf "\n"
  _sleep 0.4
  eval "$cmd"
  _sleep 1.2
}

clear
# ── Intro ─────────────────────────────────────────────────────────────────────
echo ""; echo ""
printf "${G}${B}        ██████  ██    ██  ██████   ██████  ██\n"
printf "        ██   ██ ██    ██ ██       ██    ██ ██\n"
printf "        ██████  ██    ██ ██   ███ ██    ██ ██\n"
printf "        ██   ██ ██    ██ ██    ██ ██    ██ ██\n"
printf "        ██   ██  ██████   ██████   ██████  ███████${X}\n"
echo ""
say "        Tu orquestador de agentes Claude. Apoyo para las decisiones que importan." "$GR"
_sleep 1.5

card "1 · Una sola máquina, tu centro de operaciones"
say "Rugol corre local. Sin nube, sin Docker. Veamos qué hay vivo:" "$P"
_sleep 0.5
run "rugol version"
run "rugol status"
say "Core y dashboard sanos. Todo en tu propia máquina." "$GR"

card "2 · Un bot de Telegram por proyecto"
say "Cada proyecto tiene su PROPIO bot. Token propio, agente propio, memoria propia." "$P"
_sleep 0.5
run "rugol bot list"
say "Dos contactos distintos en tu teléfono. Independientes de verdad." "$GR"
_sleep 0.5
say "Agregar otro es una línea:  rugol bot add  → pegás el token, elegís el agente." "$GR"

card "3 · La memoria es un cerebro navegable"
say "Cada agente recuerda en markdown. Y las memorias se enlazan entre sí." "$P"
_sleep 0.5
MEM="$RUGOL_HOME/app/agent-memory/assistant/MEMORY.md"
if [ -f "$MEM" ]; then
  run "cat ~/.rugol/app/agent-memory/assistant/MEMORY.md"
  say "Esos [[wikilinks]] son aristas. Apuntás Obsidian a esta carpeta…" "$GR"
  _sleep 0.4
  run "rugol vault"
  say "…y ves la red de todo lo que aprendieron tus agentes, como un cerebro." "$GR"
else
  say "(todavía sin memorias — hablale a un agente y volvé)" "$GR"
fi

card "4 · Equipos listos para clonar"
say "Plantillas que son departamentos completos. Mi favorita: Sesgo Útil." "$P"
_sleep 0.5
run "curl -s $CORE/api/templates | $PY -c \"import sys,json; [print('   •', t['title'], '—', str(t['agent_count'])+' agentes') for t in json.load(sys.stdin)]\""
say "Sesgo Útil: 5 agentes que convierten papers de economía conductual en columnas." "$GR"

card "5 · Los agentes mejoran su propio prompt"
if [ "$FAST" = "1" ]; then
  say "Self-improving (Soul-3): el agente propone mejoras a SÍ mismo, vos aprobás." "$P"
  _sleep 0.4
  printf "${GR}❯${X} rugol evolve assistant\n"
  say "   → propone versiones nuevas de su prompt; las revisás en el dashboard." "$GR"
else
  say "El agente propone mejoras a su propio prompt. Vos tenés la última palabra." "$P"
  _sleep 0.4
  run "rugol evolve assistant"
fi
say "Nada se aplica solo. El humano siempre en el loop." "$GR"

# ── Cierre ──────────────────────────────────────────────────────────────────
card "Rugol · open-source · MIT"
say "Una línea para instalar. Un comando para todo." "$P"
echo ""
printf "   ${B}curl -fsSL https://raw.githubusercontent.com/EduardoMoraga/rugol/main/installer/install.sh | bash${X}\n"
echo ""
say "github.com/EduardoMoraga/rugol" "$C"
echo ""; echo ""
_sleep 2
