"""Curated project templates (Capa 6).

Each template is a fully-formed Proposal that can be cloned with one click —
project + team + skills + schedules + a curated user-facing story explaining
who it's for and what it produces. Templates are the front door for non-tech
users: they don't need to write a prompt, they pick a template that resembles
their life.
"""
from .catalog import CATALOG, Template, get_template

__all__ = ["CATALOG", "Template", "get_template"]
