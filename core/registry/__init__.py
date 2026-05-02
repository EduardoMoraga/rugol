"""Filesystem registry — auto-loads agents/*.md and skills/*.md."""
from .loader import load_agent_file, load_skill_file
from .watcher import RegistryWatcher

__all__ = ["load_agent_file", "load_skill_file", "RegistryWatcher"]
