"""Mantenimiento periódico — lo que no puede colgar del arranque.

Rugol está pensado para una máquina que queda prendida: un NUC en un rincón,
meses sin reiniciarse. Todo lo que se hacía "al arrancar" no se hacía nunca:

· El respaldo de la base sólo salía en `startup_recovery`. Dos meses de uptime
  = un respaldo de dos meses. Es decir, ninguno: cuando lo necesitás, no sirve.
· Los logs sólo rotaban al arrancar (ver `core/logging_setup.py`).
· Nada barría los respaldos viejos ni los logs de generaciones anteriores.

Este módulo corre cada hora desde el scheduler y hace lo que hay que hacer
según el reloj, no según el último reinicio.
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_EVERY_HOURS = 24
KEEP_BACKUPS = 7
# Los logs los rota Python (logging_setup). Acá sólo barremos lo que quedó de
# esquemas viejos o de la rotación de la shell.
LOG_ATTIC_PATTERNS = ("*.log.1", "*.log.viejo", "*.out.log.1", "*.err.log.1")
LOG_ATTIC_MAX_AGE_DAYS = 14

_last_backup_at: float = 0.0


@dataclass
class MaintenanceReport:
    backup: str | None = None
    backups_pruned: list[str] = field(default_factory=list)
    logs_pruned: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _logs_dir() -> Path | None:
    from core.config import data_dir

    candidato = data_dir().parent / "logs"
    return candidato if candidato.is_dir() else None


def _prune_backups(report: MaintenanceReport) -> None:
    from core.config import data_dir

    carpeta = data_dir() / "backups"
    if not carpeta.is_dir():
        return
    respaldos = sorted(carpeta.glob("rugol-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for viejo in respaldos[KEEP_BACKUPS:]:
        try:
            viejo.unlink()
            report.backups_pruned.append(viejo.name)
        except OSError as e:
            report.errors.append(f"no se pudo borrar {viejo.name}: {e}")


def _prune_log_attic(report: MaintenanceReport) -> None:
    carpeta = _logs_dir()
    if carpeta is None:
        return
    corte = time.time() - LOG_ATTIC_MAX_AGE_DAYS * 86400
    for patron in LOG_ATTIC_PATTERNS:
        for viejo in carpeta.glob(patron):
            try:
                if viejo.stat().st_mtime < corte:
                    tamaño = viejo.stat().st_size
                    viejo.unlink()
                    report.logs_pruned.append(f"{viejo.name} ({tamaño // 1048576} MB)")
            except OSError as e:
                report.errors.append(f"no se pudo borrar {viejo.name}: {e}")


def run_maintenance(force_backup: bool = False) -> MaintenanceReport:
    """Un ciclo de mantenimiento. No levanta: devuelve lo que hizo y lo que falló."""
    global _last_backup_at
    from core.resilience import backup_database

    report = MaintenanceReport()

    vencido = (time.time() - _last_backup_at) >= BACKUP_EVERY_HOURS * 3600
    if force_backup or vencido:
        try:
            destino = backup_database()
            if destino:
                report.backup = destino
                _last_backup_at = time.time()
        except Exception as e:
            report.errors.append(f"respaldo: {e}")
            logger.warning("mantenimiento: el respaldo falló", exc_info=True)

    _prune_backups(report)
    _prune_log_attic(report)

    if report.backup or report.backups_pruned or report.logs_pruned:
        logger.info(
            "mantenimiento: respaldo=%s respaldos_borrados=%d logs_borrados=%d",
            report.backup or "-", len(report.backups_pruned), len(report.logs_pruned),
        )
    return report


def note_startup_backup() -> None:
    """`startup_recovery` ya respaldó al arrancar: no dupliquemos en la primera hora."""
    global _last_backup_at
    _last_backup_at = time.time()
