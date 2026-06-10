"""Memory graph builder — nodes, wikilink edges, concepts, degree.

The dashboard's Obsidian-style view depends on these invariants:
- every agent with memories appears as an agent node owning its memories;
- a [[wikilink]] that matches another memory's name becomes a memory→memory
  edge; an unresolved one becomes a shared concept node (cross-agent glue);
- self-links and duplicate edges are dropped; degree is precomputed.
"""
from __future__ import annotations

import core.memory.store as store
from core.memory.graph import build_memory_graph, extract_wikilinks


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_repo_root", lambda: tmp_path)


def test_extract_wikilinks_variants():
    body = "Ver [[ancla]] y [[ancla|alias]] y [[otra#seccion]] y [[ancla]] repetida."
    assert extract_wikilinks(body) == ["ancla", "otra"]


def test_graph_links_memories_by_name(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    store.add_memory("scout", "sesgo_de_anclaje", "d", "El primer numero manda.", kind="reference")
    store.add_memory("scout", "pricing_con_ia", "d", "Aplica [[sesgo_de_anclaje]] al pricing.", kind="project")
    g = build_memory_graph()
    links = [e for e in g["edges"] if e["type"] == "link"]
    assert len(links) == 1
    assert links[0]["source"].endswith("pricing-con-ia")
    assert links[0]["target"].endswith("sesgo-de-anclaje")
    owns = [e for e in g["edges"] if e["type"] == "owns"]
    assert len(owns) == 2  # agente → cada memoria
    assert g["stats"]["agents"] == 1 and g["stats"]["memories"] == 2


def test_unresolved_wikilink_becomes_shared_concept(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    store.add_memory("scout", "m1", "d", "Esto toca [[Ruido Kahneman]].")
    store.add_memory("editor", "m2", "d", "Tambien sobre [[ruido kahneman]].")
    g = build_memory_graph()
    concepts = [n for n in g["nodes"] if n["type"] == "concept"]
    assert len(concepts) == 1  # normalizado case-insensitive → un solo nodo
    cid = concepts[0]["id"]
    incoming = [e for e in g["edges"] if e["target"] == cid and e["type"] == "link"]
    assert len(incoming) == 2  # ambos agentes conectados al mismo concepto


def test_self_links_and_duplicates_dropped(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    store.add_memory("a", "solo", "d", "Me cito [[solo]] y de nuevo [[solo]].")
    g = build_memory_graph()
    assert [e for e in g["edges"] if e["type"] == "link"] == []


def test_degree_present_on_all_nodes(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    store.add_memory("a", "hub", "d", "x")
    g = build_memory_graph()
    assert all("degree" in n for n in g["nodes"])
    agent = next(n for n in g["nodes"] if n["type"] == "agent")
    assert agent["degree"] == 1
