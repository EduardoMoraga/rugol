#!/usr/bin/env python3
"""`rugol` en una terminal: hablarle a un agente desde donde estás trabajando.

Rugol tenía tres puertas de entrada —Telegram, el dashboard, el cron— y ninguna
servía para el momento en que uno está adentro de una carpeta con un problema.
Para eso había que abrir el navegador, encontrar el agente, y explicarle por
escrito dónde estaban los archivos que uno tenía delante.

Este cliente cierra esa brecha, y lo hace apoyándose en algo que ya existía: la
API completa —lanzar, transmitir en vivo, retomar la conversación, cancelar—
estaba construida y probada. Faltaba el programa que se sentara en la terminal
y la usara. No hay motor nuevo acá; hay un cliente.

Lo que lo hace orgánico es una sola decisión: **la carpeta elige el agente**. Si
estás parado en la carpeta de trabajo de un proyecto, le hablás al equipo de ese
proyecto sin decir su nombre. Es la diferencia entre una herramienta que usás y
una que está donde estás.

Uso:
    rugol chat                      # conversación, agente según la carpeta
    rugol chat analista             # conversación con un agente concreto
    rugol run analista "pregunta"   # una sola vuelta, y sale

Ctrl-C corta la corrida en curso (no la sesión). Ctrl-D sale.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover - el instalador siempre lo trae
    print("falta httpx — corré 'rugol update'", file=sys.stderr)
    raise SystemExit(1) from None


CORE = f"http://127.0.0.1:{os.environ.get('CORE_PORT', '8000')}"

# Colores sólo si hay terminal de verdad. Redirigido a un archivo, texto plano.
_TTY = sys.stdout.isatty()
def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _TTY else s

DIM = lambda s: _c("2", s)          # noqa: E731
BOLD = lambda s: _c("1", s)         # noqa: E731
ACCENT = lambda s: _c("38;5;173", s)  # noqa: E731
RED = lambda s: _c("31", s)         # noqa: E731


def _get(client: httpx.Client, path: str):
    r = client.get(f"{CORE}{path}", timeout=10)
    r.raise_for_status()
    return r.json()


def core_up(client: httpx.Client) -> bool:
    """¿Contesta NUESTRO core?

    La marca importa: si el puerto lo tiene otra aplicación, su respuesta
    pasaría por buena y el chat quedaría hablándole a un desconocido.
    """
    try:
        return _get(client, "/api/health").get("service") == "rugol-core"
    except Exception:
        return False


def match_project(projects: list[dict], cwd: Path) -> dict | None:
    """El proyecto cuya carpeta de trabajo contiene a ésta.

    Gana la carpeta MÁS ESPECÍFICA: si `/datos` y `/datos/mx` son dos
    proyectos, parado en `/datos/mx/agosto` corresponde el segundo. Elegir el
    más general sería hablarle al equipo equivocado justo cuando bajaste al
    detalle, que es cuando más importa.
    """
    try:
        aquí = cwd.resolve()
    except OSError:
        return None
    mejor, profundidad = None, -1
    for p in projects:
        crudo = (p.get("workspace_dir") or "").strip()
        if not crudo:
            continue
        try:
            carpeta = Path(crudo).resolve()
        except OSError:
            continue
        if aquí == carpeta or carpeta in aquí.parents:
            if len(carpeta.parts) > profundidad:
                mejor, profundidad = p, len(carpeta.parts)
    return mejor


def pick_agent(client: httpx.Client, wanted: str | None) -> dict:
    """El agente con el que vamos a hablar.

    Orden: el que pediste; el del proyecto cuya carpeta de trabajo es ésta
    (o la contiene); el DEFAULT_AGENT; y si nada de eso resuelve, el único
    agente que haya. Fallar es la última opción, no la primera.
    """
    agents = _get(client, "/api/agents")
    if not agents:
        raise SystemExit("No hay agentes todavía. Creá uno en el dashboard.")

    if wanted:
        for a in agents:
            if a["name"].lower() == wanted.lower():
                return a
        nombres = ", ".join(sorted(a["name"] for a in agents))
        raise SystemExit(f"No existe el agente '{wanted}'. Hay: {nombres}")

    mejor = match_project(_get(client, "/api/projects"), Path.cwd())
    if mejor:
        del_proyecto = [a for a in agents if a.get("project_slug") == mejor["slug"]]
        if del_proyecto:
            return del_proyecto[0]

    por_defecto = os.environ.get("DEFAULT_AGENT", "").strip()
    for a in agents:
        if a["name"].lower() == por_defecto.lower():
            return a
    if len(agents) == 1:
        return agents[0]
    nombres = ", ".join(sorted(a["name"] for a in agents))
    raise SystemExit(
        f"No sé a quién hablarle desde acá. Elegí uno:  rugol chat <agente>\n  Hay: {nombres}"
    )


class Turn:
    """Una vuelta de conversación: lanzar, transmitir, terminar.

    El estado vive acá y no en variables sueltas porque Ctrl-C tiene que poder
    cancelar la corrida EN CURSO sin matar la sesión, y para eso hace falta
    saber cuál es.
    """

    def __init__(self, client: httpx.Client, agent: dict, session_id: str | None):
        self.client, self.agent, self.session_id = client, agent, session_id
        self.run_id: int | None = None

    def ask(self, prompt: str, *, engine: str | None = None, quiet: bool = False) -> str:
        cuerpo: dict = {"prompt": prompt}
        if self.session_id:
            cuerpo["session_id"] = self.session_id
        if engine:
            cuerpo["engine"] = engine
        r = self.client.post(f"{CORE}/api/agents/{self.agent['id']}/run", json=cuerpo, timeout=30)
        if r.status_code >= 400:
            detalle = r.json().get("detail", r.text) if "json" in r.headers.get("content-type", "") else r.text
            raise RuntimeError(str(detalle))
        self.run_id = r.json()["run_id"]
        try:
            return self._stream(quiet=quiet)
        finally:
            self.run_id = None

    def _stream(self, *, quiet: bool) -> str:
        """Consume el SSE de esta corrida y va escribiendo lo que llega.

        Mostrar las herramientas es la ventaja real de la terminal sobre el
        chat del dashboard, que sólo enseña el texto final formándose: acá se
        ve QUÉ archivo abrió y qué comando corrió, que es la mitad de la
        información cuando algo sale distinto a lo esperado.
        """
        salida: list[str] = []
        url = f"{CORE}/api/stream?run_id={self.run_id}&topics=run:*"
        with self.client.stream("GET", url, timeout=None) as resp:
            for linea in resp.iter_lines():
                if not linea or not linea.startswith("data:"):
                    continue
                try:
                    evento = json.loads(linea[5:].strip())
                except json.JSONDecodeError:
                    continue
                topico = evento.get("topic", "")
                data = evento.get("data") or {}
                if topico == "run:message" and data.get("delta"):
                    salida.append(data["delta"])
                    if not quiet:
                        sys.stdout.write(data["delta"])
                        sys.stdout.flush()
                elif topico == "run:tool" and not quiet:
                    nombre = data.get("name") or data.get("tool") or "tool"
                    sys.stdout.write(DIM(f"\n  · {nombre}\n"))
                    sys.stdout.flush()
                elif topico in ("run:completed", "run:failed", "run:cancelled", "run:interrupted"):
                    break
        # El texto final de la base es la fuente de verdad: los deltas pueden
        # perderse si el SSE se reconecta a mitad de camino.
        try:
            fila = _get(self.client, f"/api/runs/{self.run_id}")
            self.session_id = fila.get("session_id") or self.session_id
            if fila.get("status") == "failed":
                raise RuntimeError(fila.get("error_message") or "la corrida falló")
            final = (fila.get("final_text") or "").strip()
            if final and not quiet and not "".join(salida).strip():
                print(final)
            return final or "".join(salida)
        except httpx.HTTPError:
            return "".join(salida)

    def cancel(self) -> None:
        if self.run_id is None:
            return
        try:
            self.client.post(f"{CORE}/api/runs/{self.run_id}/cancel", timeout=10)
        except httpx.HTTPError:
            pass


def _prompt_label(agent: dict) -> str:
    return ACCENT("› ")


def repl(client: httpx.Client, agent: dict, engine: str | None) -> int:
    print()
    print(f"{BOLD('Rugol')} · {agent['name']} · {agent.get('model', '?')} · {DIM(str(Path.cwd()))}")
    print(DIM("Escribí tu consulta. Ctrl-C corta la corrida, Ctrl-D sale."))
    print()
    turno = Turn(client, agent, None)
    while True:
        try:
            linea = input(_prompt_label(agent)).strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            continue
        if not linea:
            continue
        if linea in ("/salir", "/exit", "/quit"):
            return 0
        try:
            print()
            turno.ask(linea, engine=engine)
            print("\n")
        except KeyboardInterrupt:
            # Ctrl-C corta la CORRIDA, no la sesión. Es la diferencia entre
            # "me arrepentí de esta pregunta" y "quiero irme".
            turno.cancel()
            print(DIM("\n  (corrida cancelada)\n"))
        except RuntimeError as e:
            print(RED(f"\n  {e}\n"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="rugol chat", add_help=True)
    ap.add_argument("words", nargs="*", help="[agente] [pregunta]")
    ap.add_argument("--engine", choices=["claude", "codex"], help="motor sólo para esta sesión")
    args = ap.parse_args(argv)

    with httpx.Client(follow_redirects=False) as client:
        if not core_up(client):
            print(RED(f"El core no responde en {CORE}. Levantalo con:  rugol up"), file=sys.stderr)
            return 1

        # ¿La primera palabra es un agente o ya es la pregunta?
        #
        # Obligar a nombrar al agente rompe justo lo que hace útil a esto: si
        # la carpeta ya sabe con quién hablás, escribir el nombre es ceremonia.
        # Así que se decide mirando: sólo es un agente si EXISTE uno con ese
        # nombre. "analista ¿cuántas filas?" y "¿cuántas filas?" funcionan las
        # dos, y nadie tiene que aprender la diferencia.
        palabras = list(args.words)
        nombres = {a["name"].lower() for a in _get(client, "/api/agents")}
        pedido = None
        if palabras and palabras[0].lower() in nombres:
            pedido = palabras.pop(0)

        agente = pick_agent(client, pedido)
        args.prompt = palabras
        if args.prompt:
            turno = Turn(client, agente, None)
            try:
                turno.ask(" ".join(args.prompt), engine=args.engine)
                print()
                return 0
            except KeyboardInterrupt:
                turno.cancel()
                return 130
            except RuntimeError as e:
                print(RED(str(e)), file=sys.stderr)
                return 1
        return repl(client, agente, args.engine)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
