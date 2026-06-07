"""Obsidian-native memory: aliases + wikilinks make the folder a graph.

The point of these tests is that pointing Obsidian at agent-memory/ yields
a real graph (nodes connected by edges), not a flat list of orphan notes.
That requires: (1) each note carries an `aliases` frontmatter equal to its
name so `[[name]]` resolves; (2) `related` renders as `[[wikilinks]]`;
(3) the MEMORY.md index links to every note with wikilinks.
"""
from __future__ import annotations

import core.memory.store as store


def _isolate(tmp_path, monkeypatch):
    """Point the store at a temp repo root so tests never touch real memory."""
    monkeypatch.setattr(store, "_repo_root", lambda: tmp_path)


def test_alias_frontmatter_lets_wikilinks_resolve(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    mem = store.add_memory(
        "scout", name="sesgo_de_anclaje",
        description="el primer número ancla la negociación",
        content="Cuerpo de la memoria.", kind="reference",
    )
    raw = (store.memory_dir("scout") / mem.file).read_text()
    # Obsidian resolves [[sesgo_de_anclaje]] via this alias line.
    assert "aliases: [sesgo_de_anclaje]" in raw


def test_related_renders_as_wikilinks(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    mem = store.add_memory(
        "scout", name="arquitectura_de_decisiones",
        description="cómo el diseño del entorno cambia la decisión",
        content="Idea central.", kind="project",
        related=["sesgo_de_anclaje", "ruido_kahneman"],
    )
    body = (store.memory_dir("scout") / mem.file).read_text()
    assert "**Relacionadas:**" in body
    assert "[[sesgo_de_anclaje]]" in body
    assert "[[ruido_kahneman]]" in body


def test_related_accepts_comma_string(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    mem = store.add_memory(
        "scout", name="nudge", description="empujón",
        content="x", kind="note", related="a, b ,c",
    )
    body = (store.memory_dir("scout") / mem.file).read_text()
    assert "[[a]]" in body and "[[b]]" in body and "[[c]]" in body


def test_index_uses_wikilinks_grouped_by_kind(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    store.add_memory("scout", name="hecho_uno", description="d1", content="c1", kind="reference")
    store.add_memory("scout", name="idea_dos", description="d2", content="c2", kind="project")
    index = (store.memory_dir("scout") / "MEMORY.md").read_text()
    assert "## reference" in index
    assert "## project" in index
    # Wikilink form [[stem|name]] so the index node connects to each note.
    assert "[[" in index and "|hecho_uno]]" in index


def test_no_duplicate_related_footer(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    mem = store.add_memory(
        "scout", name="x", description="d",
        content="cuerpo\n\n**Relacionadas:** [[ya]]", kind="note",
        related=["otro"],
    )
    body = (store.memory_dir("scout") / mem.file).read_text()
    # Body already had a Relacionadas line — don't append a second one.
    assert body.count("**Relacionadas:**") == 1
