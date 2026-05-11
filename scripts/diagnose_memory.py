"""One-shot memory diagnostic.

Run:
    cd C:\\Moragent\\rogologo
    .\\.venv\\Scripts\\python.exe scripts\\diagnose_memory.py

What it does:
1. Connects to the running backend on http://127.0.0.1:8000.
2. Lists every agent with its whitelist + MCP config — the FIRST clue for
   why save_memory might not be invocable.
3. Picks the agent named 'gugol' (or asks if missing).
4. Fires a `POST /api/agents/{id}/run` with a hard "recuerda" prompt.
5. Polls the run until it finishes.
6. Prints the final_text the model emitted.
7. Lists files in `agent-memory/<gugol>/` before and after.
8. Tells you in plain Spanish whether memory was saved.

You DO NOT need to know any commands beyond running this script.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


BASE = "http://127.0.0.1:8000"
TEST_PROMPT = (
    "Recuerda que prefiero respuestas cortas y sin tablas grandes. "
    "Esto es un test del sistema de memoria — invocá save_memory."
)
TARGET_AGENT = "gugol"


def _get(path: str) -> dict | list:
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def _post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _list_memory_files(agent_name: str) -> list[str]:
    repo_root = Path(__file__).resolve().parent.parent
    folder = repo_root / "agent-memory" / agent_name.lower()
    if not folder.exists():
        return []
    return sorted(p.name for p in folder.glob("*.md"))


def banner(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main() -> int:
    # 1. Health
    banner("1. ¿El backend está corriendo?")
    try:
        h = _get("/api/health")
        print(f"  OK · versión {h.get('version')} · runs activos {h.get('active_runs')}")
    except (urllib.error.URLError, ConnectionRefusedError) as e:
        print(f"  ✗ Backend NO responde en {BASE} — arranca uvicorn primero.")
        print(f"    Error: {e}")
        return 1

    # 2. List agents + config
    banner("2. Config de cada agente (tools whitelist + MCP servers)")
    agents = _get("/api/agents")
    target = None
    for a in agents:
        tools_str = a.get("tools") or "[preset]"
        mcp_str = list((a.get("mcp_servers") or {}).keys()) or "[ninguno]"
        marker = " ← TARGET" if a["name"] == TARGET_AGENT else ""
        print(f"  #{a['id']:>2}  {a['name']:<28}  tools={tools_str}  mcp={mcp_str}{marker}")
        if a["name"] == TARGET_AGENT:
            target = a
    if target is None:
        print()
        print(f"  ✗ No encuentro un agente llamado '{TARGET_AGENT}'.")
        print(f"    Edita TARGET_AGENT al principio del script y vuelvé a correr.")
        return 1

    # 3. Memory before
    banner(f"3. Estado de la memoria de '{TARGET_AGENT}' ANTES del test")
    before = _list_memory_files(TARGET_AGENT)
    if before:
        print(f"  {len(before)} archivo(s):")
        for n in before:
            print(f"   - {n}")
    else:
        print("  (carpeta agent-memory/{}/ vacía o no existe)".format(TARGET_AGENT))

    # 4. Fire test run
    banner(f"4. Disparando run de prueba contra agente #{target['id']} ({TARGET_AGENT})")
    print(f"  Prompt: {TEST_PROMPT}")
    r = _post(f"/api/agents/{target['id']}/run", {"prompt": TEST_PROMPT})
    run_id = r.get("run_id")
    if not run_id:
        print(f"  ✗ El backend no devolvió run_id: {r}")
        return 1
    print(f"  run_id = {run_id} · esperando a que termine (hasta 90s)...")

    # 5. Wait for completion
    final = None
    for i in range(45):
        time.sleep(2)
        rd = _get(f"/api/runs/{run_id}")
        st = rd.get("status")
        if i % 5 == 0:
            print(f"   [{(i+1)*2:>3}s] status={st}")
        if st in ("completed", "failed", "cancelled"):
            final = rd
            break
    if final is None:
        print("  ✗ Timeout después de 90s. El run sigue corriendo.")
        return 1

    banner("5. Resultado del run")
    print(f"  status: {final.get('status')}")
    print(f"  track : {final.get('track') or '-'} (conf={final.get('classifier_confidence')})")
    print(f"  cost  : ${final.get('cost_usd', 0):.4f}")
    print()
    print("  --- Lo que dijo el agente ---")
    print(f"  {final.get('final_text') or '(vacío)'}")

    # 6. Wait extra 15s for Soul-1.5 checkpoint to finish (fire-and-forget)
    banner("6. Esperando 20s adicionales por si Soul-1.5 (checkpoint) está corriendo")
    time.sleep(20)

    # 7. Memory after
    after = _list_memory_files(TARGET_AGENT)
    new_files = [f for f in after if f not in before]

    banner(f"7. Estado de la memoria de '{TARGET_AGENT}' DESPUÉS")
    if after:
        for n in after:
            mark = " ← NUEVO" if n in new_files else ""
            print(f"   - {n}{mark}")
    else:
        print("  (carpeta sigue vacía)")

    # 8. Verdict
    banner("8. Veredicto")
    if new_files:
        print(f"  ✓ FUNCIONÓ. Se guardaron {len(new_files)} memoria(s) nueva(s).")
        repo_root = Path(__file__).resolve().parent.parent
        for n in new_files:
            f = repo_root / "agent-memory" / TARGET_AGENT.lower() / n
            print()
            print(f"  --- {n} ---")
            try:
                print("  " + f.read_text(encoding="utf-8").replace("\n", "\n  "))
            except Exception as e:
                print(f"  (no pude leer: {e})")
        return 0
    else:
        print("  ✗ NO se guardó ninguna memoria.")
        print()
        print("  Datos críticos para diagnóstico:")
        print(f"  - Versión backend  : {_get('/api/health').get('version')}")
        print(f"  - Agente target    : id={target['id']}  name={target['name']}")
        print(f"  - tools whitelist  : {target.get('tools') or '[preset]'}")
        print(f"  - mcp_servers conf : {list((target.get('mcp_servers') or {}).keys())}")
        print(f"  - run_id del test  : {run_id}")
        print(f"  - final_text       : {(final.get('final_text') or '')[:200]}")
        print()
        print("  Copia ESTE BLOQUE entero y pásamelo en el chat.")
        return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n(cancelado por usuario)")
        sys.exit(130)
