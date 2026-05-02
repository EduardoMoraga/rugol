"""Shared memory graph (triple store) — read/write tools exposed to agents."""
from .store import OntologyStore, get_ontology

__all__ = ["OntologyStore", "get_ontology"]
