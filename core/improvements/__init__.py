"""Self-improving loop — reflection prompt + diff queue + human approval."""
from .trigger import is_due
from .reflector import propose_improvement

__all__ = ["is_due", "propose_improvement"]
