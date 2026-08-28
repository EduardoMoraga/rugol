"""Lo que no puede colgar del arranque.

Rugol vive en una máquina que no se reinicia. Se encontró una instalación con
dos meses de uptime: un `core.log` de 143 MB y un respaldo de la base de dos
meses —o sea, ninguno—. La rotación y el respaldo existían; corrían al arrancar,
y la máquina no arranca.
"""
from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler

import pytest


@pytest.fixture
def logs_limpios():
    """Pizarra limpia ANTES, y estado restaurado después.

    Antes sólo limpiaba al salir, y eso hacía que estos tests dependieran del
    orden de importación: `core/main.py` configura el logging como efecto de
    importarlo, así que bastaba con que otro test importara la app primero
    para que `setup_logging()` viera el handler ya puesto, devolviera None y
    todos los asserts de acá se cayeran.

    Pasaban por suerte. Un test que depende de quién corrió antes no está
    verificando lo que dice verificar.
    """
    root = logging.getLogger()
    previos = list(root.handlers)
    nivel = root.level
    # Sacamos los handlers de archivo que otro import haya dejado. Se guardan
    # para devolverlos: apagarle el log al resto de la suite sería peor.
    apartados = [h for h in previos if isinstance(h, logging.FileHandler)]
    for h in apartados:
        root.removeHandler(h)
    yield
    for h in list(root.handlers):
        if h not in previos:
            h.close()
            root.removeHandler(h)
    for h in apartados:
        if h not in root.handlers:
            root.addHandler(h)
    root.setLevel(nivel)


def test_the_app_log_rotates_without_a_restart(tmp_path, monkeypatch, logs_limpios):
    """El techo del log no puede depender de que alguien reinicie."""
    import core.logging_setup as ls

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(ls, "MAX_BYTES", 2048)
    monkeypatch.setattr(ls, "BACKUPS", 2)

    destino = ls.setup_logging()
    assert destino is not None
    log = logging.getLogger("test.rotacion")
    for i in range(400):
        log.info("línea de relleno número %d con texto para llenar el archivo", i)

    generaciones = sorted(destino.parent.glob("core.app.log*"))
    assert len(generaciones) > 1, "escribió de más y nunca rotó"
    for g in generaciones:
        assert g.stat().st_size < 20 * 1024, f"{g.name} creció sin techo"
    # El techo total es maxBytes * (backups + 1), no infinito.
    assert len(generaciones) <= ls.BACKUPS + 1


def test_setup_logging_is_idempotent(tmp_path, monkeypatch, logs_limpios):
    """Importar dos veces no puede dejar dos handlers escribiendo el mismo archivo."""
    import core.logging_setup as ls

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path / "data"))
    assert ls.setup_logging() is not None
    assert ls.setup_logging() is None
    rotativos = [h for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotativos) == 1


def test_a_log_dir_we_cannot_write_does_not_break_boot(tmp_path, monkeypatch, logs_limpios):
    import core.logging_setup as ls

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path / "data"))
    # Un archivo donde se espera una carpeta: abrir el log es imposible.
    bloqueado = tmp_path / "bloqueado"
    bloqueado.write_text("no soy una carpeta")
    monkeypatch.setattr(ls, "log_file", lambda: bloqueado / "core.app.log")

    assert ls.setup_logging() is None  # no levanta: el arranque sigue
    # Y la consola queda igual, así que el operador no se queda a ciegas.
    assert any(isinstance(h, logging.StreamHandler) for h in logging.getLogger().handlers)


def test_backups_are_taken_by_the_clock_not_by_the_boot(tmp_path, monkeypatch):
    import core.maintenance as mt

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    llamadas = []

    def falso_backup():
        llamadas.append(1)
        return str(tmp_path / "backups" / f"rugol-{len(llamadas)}.db")

    monkeypatch.setattr("core.resilience.backup_database", falso_backup)

    mt._last_backup_at = 0.0
    assert mt.run_maintenance().backup is not None, "el primer ciclo debe respaldar"
    assert mt.run_maintenance().backup is None, "no respalda dos veces en la misma hora"

    # Pasado el intervalo, vuelve a respaldar sin que nadie reinicie nada.
    mt._last_backup_at = time.time() - (mt.BACKUP_EVERY_HOURS + 1) * 3600
    assert mt.run_maintenance().backup is not None


def test_backups_do_not_pile_up_forever(tmp_path, monkeypatch):
    import core.maintenance as mt

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    carpeta = tmp_path / "backups"
    carpeta.mkdir()
    for i in range(mt.KEEP_BACKUPS + 5):
        f = carpeta / f"rugol-{i:03d}.db"
        f.write_bytes(b"x" * 100)
        import os
        os.utime(f, (time.time() - (100 - i) * 60,) * 2)

    monkeypatch.setattr("core.resilience.backup_database", lambda: None)
    mt._last_backup_at = time.time()
    report = mt.run_maintenance()

    quedan = sorted(carpeta.glob("rugol-*.db"))
    assert len(quedan) == mt.KEEP_BACKUPS
    assert len(report.backups_pruned) == 5
    # Se conservan los MÁS NUEVOS. Barrer al revés sería peor que no barrer.
    assert quedan[-1].name == f"rugol-{mt.KEEP_BACKUPS + 4:03d}.db"


def test_the_old_143mb_log_gets_swept(tmp_path, monkeypatch):
    """El caso literal que se encontró en la instalación real."""
    import os

    import core.maintenance as mt

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data").mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()

    viejo = logs / "core.log.viejo"
    viejo.write_bytes(b"x" * 1024)
    os.utime(viejo, (time.time() - 30 * 86400,) * 2)
    reciente = logs / "core.log.1"
    reciente.write_bytes(b"x" * 1024)

    monkeypatch.setattr("core.resilience.backup_database", lambda: None)
    mt._last_backup_at = time.time()
    report = mt.run_maintenance()

    assert not viejo.exists(), "un log de un mes no tiene por qué seguir ocupando disco"
    assert reciente.exists(), "el de ayer puede hacer falta para diagnosticar"
    assert any("core.log.viejo" in x for x in report.logs_pruned)
    # El log vivo NUNCA se toca.
    assert not (logs / "core.log").exists()


def test_a_failing_backup_does_not_stop_the_sweep(tmp_path, monkeypatch):
    import core.maintenance as mt

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    (tmp_path / "backups").mkdir()
    for i in range(mt.KEEP_BACKUPS + 2):
        (tmp_path / "backups" / f"rugol-{i:03d}.db").write_bytes(b"x")

    def explota():
        raise OSError("disco lleno")

    monkeypatch.setattr("core.resilience.backup_database", explota)
    mt._last_backup_at = 0.0
    report = mt.run_maintenance()

    assert report.backup is None
    assert report.errors, "el fallo tiene que quedar dicho"
    assert len(report.backups_pruned) == 2, (
        "justamente cuando el disco está lleno es cuando hay que barrer"
    )


@pytest.mark.asyncio
async def test_the_scheduler_registers_maintenance(tmp_path, monkeypatch):
    """Que el job exista de verdad, no sólo la función."""
    from core.scheduler.scheduler import RugolScheduler

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    sch = RugolScheduler(tmp_path / "sched.db")
    sch.add_maintenance_job(hours=1)
    ids = [j["id"] for j in sch.list_jobs()]
    assert "internal:maintenance" in ids


@pytest.mark.asyncio
async def test_maintenance_failure_never_reaches_the_scheduler(monkeypatch):
    """Un fallo de mantenimiento no puede tumbar los schedules del usuario."""
    from core.scheduler import scheduler as mod

    def explota():
        raise RuntimeError("todo mal")

    monkeypatch.setattr("core.maintenance.run_maintenance", explota)
    await mod._fire_maintenance()  # si propaga, el test falla


def test_a_detached_process_does_not_write_the_log_twice(tmp_path, monkeypatch, logs_limpios):
    """El detalle que anulaba todo el arreglo.

    El launcher redirige stdout a `core.log`. Con un handler de consola cada
    línea se escribía dos veces: una al archivo rotativo y otra a un `core.log`
    que nadie rota. El techo volvía a ser infinito por la ventana.
    """
    import io

    import core.logging_setup as ls

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "logs").mkdir()

    redirigido = io.StringIO()  # StringIO no es un tty: es el caso del launcher
    monkeypatch.setattr("sys.stdout", redirigido)

    destino = ls.setup_logging()
    assert destino is not None
    logging.getLogger("test.doble").info("una línea")

    assert redirigido.getvalue() == "", "escribió a stdout, que el launcher no rota"
    assert "una línea" in destino.read_text(encoding="utf-8")


def test_with_a_terminal_the_operator_still_sees_the_logs(tmp_path, monkeypatch, logs_limpios):
    """En desarrollo la consola es lo que el operador está mirando."""
    import io

    import core.logging_setup as ls

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "logs").mkdir()

    class ConTerminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    terminal = ConTerminal()
    monkeypatch.setattr("sys.stdout", terminal)

    assert ls.setup_logging() is not None
    logging.getLogger("test.tty").info("visible")
    assert "visible" in terminal.getvalue()


def test_the_telegram_poll_does_not_flood_the_log(tmp_path, monkeypatch, logs_limpios):
    """La causa real del log de 143 MB.

    `httpx` anotaba cada poll de Telegram a INFO: dos bots preguntando "¿algo
    nuevo?" cada segundo son ~170.000 líneas por día, y entre ellas se pierde lo
    único que importaba —el error de la corrida que falló—.
    """
    import core.logging_setup as ls

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "logs").mkdir()
    destino = ls.setup_logging()
    assert destino is not None

    logging.getLogger("httpx").info('HTTP Request: POST .../getUpdates "HTTP/1.1 200 OK"')
    logging.getLogger("httpcore.http11").info("send_request_headers.complete")
    # Un problema real de red SÍ tiene que quedar.
    logging.getLogger("httpx").warning("no se pudo conectar con api.telegram.org")
    # Y lo nuestro nunca se calla.
    logging.getLogger("core.runner.dispatch").info("corrida 42 terminada")

    escrito = destino.read_text(encoding="utf-8")
    assert "getUpdates" not in escrito
    assert "send_request_headers" not in escrito
    assert "no se pudo conectar" in escrito
    assert "corrida 42 terminada" in escrito
