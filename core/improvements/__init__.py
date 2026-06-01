"""Self-improving loop — reflection prompt + diff queue + human approval."""
from .reflector import propose_improvement
from .trigger import is_due

__all__ = ["is_due", "propose_improvement"]
