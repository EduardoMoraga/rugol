"""El log del core, con rotación real — y no atada al arranque.

Se encontró un `core.log` de 143 MB en una instalación de dos meses. La causa no
era que faltara rotación: la había, pero corría **al arrancar**. Y la máquina
para la que Rugol está pensado —un NUC que queda prendido— justamente no
arranca nunca. Todo lo que cuelga del boot no existe en la máquina que no
reinicia.

Rotar desde afuera tampoco sirve: la shell abre `core.log` con redirección y se
queda con el descriptor. Truncar por debajo deja un archivo disperso que sigue
midiendo lo mismo, y en Windows la truncada falla de plano porque
`Start-Process -RedirectStandardOutput` no comparte el handle de escritura.

Entonces Python se hace dueño de su log. `RotatingFileHandler` corta a los 20 MB
y conserva tres generaciones: 80 MB de techo, para siempre, sin depender de
reinicios ni de nadie que mire el disco. La redirección de la shell sigue
existiendo para lo que pasa *antes* de que el logging esté en pie (un traceback
de importación, un puerto ocupado), que es poco y no crece.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Ruido que no diagnostica nada. Ésta es la causa real de aquel log de 143 MB:
# `httpx` anota CADA poll de Telegram a INFO. Dos bots preguntando "¿algo
# nuevo?" cada segundo son unas 170.000 líneas por día — y entre ellas se
# pierde lo único que importaba, el error de la corrida que falló. Rotar pone
# techo al disco; callar el ruido hace que el log sirva para algo.
NOISY_LOGGERS = {
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
    "telegram.ext.Updater": logging.WARNING,
    "watchfiles": logging.WARNING,
    "apscheduler.executors.default": logging.WARNING,
}

MAX_BYTES = 20 * 1024 * 1024
BACKUPS = 3
FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def log_file() -> Path:
    from core.config import data_dir

    # Junto al resto de los logs si esa carpeta existe (instalación nativa:
    # ~/.rugol/logs), y si no, dentro del directorio de datos.
    candidato = data_dir().parent / "logs"
    carpeta = candidato if candidato.is_dir() else data_dir()
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / "core.app.log"


def setup_logging(level: int = logging.INFO) -> Path | None:
    """Consola + archivo rotativo. Devuelve el archivo, o None si no se pudo."""
    root = logging.getLogger()
    root.setLevel(level)

    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return None

    destino: Path | None = None
    try:
        destino = log_file()
        archivo = RotatingFileHandler(
            destino, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8",
        )
        archivo.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(archivo)
    except Exception:
        # Un log que no se puede escribir no puede tumbar el arranque: en ese
        # caso la consola vuelve a ser el único log, y mejor eso que nada.
        logging.getLogger(__name__).warning("no se pudo abrir el log rotativo", exc_info=True)
        destino = None

    for nombre, nivel in NOISY_LOGGERS.items():
        logging.getLogger(nombre).setLevel(nivel)

    _attach_console(root, tiene_archivo=destino is not None)
    return destino


def _attach_console(root: logging.Logger, tiene_archivo: bool) -> None:
    """Consola sólo cuando sirve de algo.

    El detalle que anulaba todo el arreglo: el launcher redirige stdout a
    `core.log`. Si dejamos un handler de consola, cada línea se escribe DOS
    veces —una al archivo rotativo y otra a un `core.log` que nadie rota— y
    volvemos al archivo de 143 MB por la ventana.

    Entonces: con terminal (desarrollo), consola sí, es lo que el operador está
    mirando. Sin terminal (arrancado por el launcher o por el autostart), el log
    de archivo es el log, y stdout queda para lo que se rompa antes de que esto
    exista.
    """
    ya = any(
        isinstance(h, logging.StreamHandler)
        and not isinstance(h, RotatingFileHandler)
        and getattr(h, "stream", None) in (sys.stdout, sys.stderr)
        for h in root.handlers
    )
    if ya:
        return
    interactivo = False
    try:
        interactivo = bool(sys.stdout and sys.stdout.isatty())
    except Exception:
        interactivo = False
    if interactivo or not tiene_archivo:
        consola = logging.StreamHandler(sys.stdout)
        consola.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(consola)
