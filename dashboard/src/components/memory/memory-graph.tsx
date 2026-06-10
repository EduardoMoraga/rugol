"use client";

/**
 * Obsidian-style force-directed memory graph.
 *
 * Custom force simulation on HTML5 Canvas — zero extra dependencies.
 * Forces: pairwise repulsion, spring along edges, soft centering gravity.
 * Interactions: drag nodes, pan empty space, wheel zoom, hover highlights
 * the neighborhood, click selects (parent shows the detail panel).
 *
 * Re-render-free animation: simulation state lives in refs; React only
 * sees the selected node via onSelect.
 */

import { useEffect, useRef } from "react";
import type { MemoryGraphData, MemoryGraphNode } from "@/lib/api";

const COLORS: Record<string, string> = {
  agent: "#a78bfa",
  user: "#60a5fa",
  feedback: "#f59e0b",
  project: "#34d399",
  reference: "#22d3ee",
  note: "#94a3b8",
  concept: "#64748b",
};

type SimNode = MemoryGraphNode & {
  x: number; y: number; vx: number; vy: number;
  r: number; color: string; fixed?: boolean;
};

function nodeColor(n: MemoryGraphNode): string {
  if (n.type === "agent") return COLORS.agent;
  if (n.type === "concept") return COLORS.concept;
  return COLORS[n.kind ?? "note"] ?? COLORS.note;
}

function nodeRadius(n: MemoryGraphNode): number {
  const base = n.type === "agent" ? 9 : n.type === "concept" ? 3.5 : 5;
  return base + Math.min(8, Math.sqrt(n.degree || 0) * 1.4);
}

export function MemoryGraphCanvas({
  data,
  agentFilter,
  search,
  selectedId,
  onSelect,
}: {
  data: MemoryGraphData;
  agentFilter: string | null;
  search: string;
  selectedId: string | null;
  onSelect: (node: MemoryGraphNode | null) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const sim = useRef<{
    nodes: SimNode[];
    edges: { source: SimNode; target: SimNode; type: string }[];
    adjacency: Map<string, Set<string>>;
    alpha: number;
    view: { x: number; y: number; scale: number };
    hovered: SimNode | null;
    dragging: SimNode | null;
    panning: boolean;
    last: { x: number; y: number };
  } | null>(null);
  const propsRef = useRef({ agentFilter, search, selectedId, onSelect });
  propsRef.current = { agentFilter, search, selectedId, onSelect };

  // (Re)build the simulation when data changes — keep old positions so a
  // refetch doesn't explode the layout.
  useEffect(() => {
    const prev = new Map(sim.current?.nodes.map((n) => [n.id, n]) ?? []);
    const nodes: SimNode[] = data.nodes.map((n, i) => {
      const old = prev.get(n.id);
      const angle = (i / Math.max(1, data.nodes.length)) * Math.PI * 2;
      const rad = 120 + (i % 7) * 40;
      return {
        ...n,
        x: old?.x ?? Math.cos(angle) * rad + (Math.random() - 0.5) * 40,
        y: old?.y ?? Math.sin(angle) * rad + (Math.random() - 0.5) * 40,
        vx: 0, vy: 0,
        r: nodeRadius(n),
        color: nodeColor(n),
      };
    });
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const edges = data.edges
      .map((e) => ({ source: byId.get(e.source)!, target: byId.get(e.target)!, type: e.type }))
      .filter((e) => e.source && e.target);
    const adjacency = new Map<string, Set<string>>();
    for (const e of edges) {
      if (!adjacency.has(e.source.id)) adjacency.set(e.source.id, new Set());
      if (!adjacency.has(e.target.id)) adjacency.set(e.target.id, new Set());
      adjacency.get(e.source.id)!.add(e.target.id);
      adjacency.get(e.target.id)!.add(e.source.id);
    }
    sim.current = {
      nodes, edges, adjacency,
      alpha: 1,
      view: sim.current?.view ?? { x: 0, y: 0, scale: 1 },
      hovered: null, dragging: null, panning: false, last: { x: 0, y: 0 },
    };
  }, [data]);

  // Reheat when the filter changes so hidden→visible nodes settle again.
  useEffect(() => { if (sim.current) sim.current.alpha = Math.max(sim.current.alpha, 0.6); },
    [agentFilter, search]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let raf = 0;
    let disposed = false;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const visible = (n: SimNode): boolean => {
      const { agentFilter } = propsRef.current;
      if (!agentFilter) return true;
      if (n.type === "agent") return n.label === agentFilter;
      if (n.type === "memory") return n.agent === agentFilter;
      // concept: visible if linked to a visible memory
      const s = sim.current!;
      const adj = s.adjacency.get(n.id);
      if (!adj) return false;
      for (const id of adj) {
        const m = s.nodes.find((x) => x.id === id);
        if (m && m.type === "memory" && m.agent === agentFilter) return true;
      }
      return false;
    };

    const toWorld = (px: number, py: number) => {
      const rect = canvas.getBoundingClientRect();
      const v = sim.current!.view;
      return {
        x: (px - rect.left - rect.width / 2) / v.scale - v.x,
        y: (py - rect.top - rect.height / 2) / v.scale - v.y,
      };
    };

    const hit = (px: number, py: number): SimNode | null => {
      const s = sim.current;
      if (!s) return null;
      const w = toWorld(px, py);
      let best: SimNode | null = null;
      let bestD = 12 / s.view.scale + 6;
      for (const n of s.nodes) {
        if (!visible(n)) continue;
        const d = Math.hypot(n.x - w.x, n.y - w.y);
        if (d < n.r + 6 / s.view.scale && d < bestD) { best = n; bestD = d; }
      }
      return best;
    };

    const tick = () => {
      const s = sim.current;
      if (!s) return;
      const vis = s.nodes.filter(visible);
      if (s.alpha > 0.012) {
        // Repulsion
        for (let i = 0; i < vis.length; i++) {
          for (let j = i + 1; j < vis.length; j++) {
            const a = vis[i], b = vis[j];
            let dx = b.x - a.x, dy = b.y - a.y;
            let d2 = dx * dx + dy * dy;
            if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
            const f = (900 * s.alpha) / d2;
            const d = Math.sqrt(d2);
            const fx = (dx / d) * f, fy = (dy / d) * f;
            if (!a.fixed) { a.vx -= fx; a.vy -= fy; }
            if (!b.fixed) { b.vx += fx; b.vy += fy; }
          }
        }
        // Springs
        for (const e of s.edges) {
          if (!visible(e.source) || !visible(e.target)) continue;
          const rest = e.type === "owns" ? 90 : 64;
          const dx = e.target.x - e.source.x, dy = e.target.y - e.source.y;
          const d = Math.max(1, Math.hypot(dx, dy));
          const f = (d - rest) * 0.035 * s.alpha;
          const fx = (dx / d) * f, fy = (dy / d) * f;
          if (!e.source.fixed) { e.source.vx += fx; e.source.vy += fy; }
          if (!e.target.fixed) { e.target.vx -= fx; e.target.vy -= fy; }
        }
        // Gravity + integrate
        for (const n of vis) {
          if (n.fixed) continue;
          n.vx -= n.x * 0.004 * s.alpha;
          n.vy -= n.y * 0.004 * s.alpha;
          n.vx *= 0.85; n.vy *= 0.85;
          n.x += n.vx; n.y += n.vy;
        }
        s.alpha *= 0.992;
      }

      // ── Draw ──
      const dpr = window.devicePixelRatio || 1;
      const W = canvas.width / dpr, H = canvas.height / dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = "#0c0f16";
      ctx.fillRect(0, 0, W, H);
      ctx.translate(W / 2, H / 2);
      ctx.scale(s.view.scale, s.view.scale);
      ctx.translate(s.view.x, s.view.y);

      const { search, selectedId } = propsRef.current;
      const q = search.trim().toLowerCase();
      const focus = s.hovered ?? (selectedId ? s.nodes.find((n) => n.id === selectedId) ?? null : null);
      const hood = focus ? new Set([focus.id, ...(s.adjacency.get(focus.id) ?? [])]) : null;

      // Edges
      for (const e of s.edges) {
        if (!visible(e.source) || !visible(e.target)) continue;
        const inHood = hood && hood.has(e.source.id) && hood.has(e.target.id);
        ctx.strokeStyle = inHood ? "rgba(220,225,255,0.55)" : "rgba(140,150,180,0.14)";
        ctx.lineWidth = (inHood ? 1.4 : 0.7) / s.view.scale;
        ctx.beginPath();
        ctx.moveTo(e.source.x, e.source.y);
        ctx.lineTo(e.target.x, e.target.y);
        ctx.stroke();
      }
      // Nodes
      for (const n of vis) {
        const matches = q ? n.label.toLowerCase().includes(q) : false;
        const dim = (hood && !hood.has(n.id)) || (q && !matches);
        ctx.globalAlpha = dim ? 0.16 : 1;
        ctx.fillStyle = n.color;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fill();
        if (n.id === selectedId || matches) {
          ctx.strokeStyle = "#e9ecf8";
          ctx.lineWidth = 1.6 / s.view.scale;
          ctx.stroke();
        }
        // Labels: agents always; others when zoomed in / focused / matching
        const showLabel =
          n.type === "agent" || s.view.scale > 1.15 ||
          (hood ? hood.has(n.id) : false) || matches || n.id === selectedId;
        if (showLabel && !dim) {
          ctx.font = `${(n.type === "agent" ? 12 : 10.5) / s.view.scale}px ui-sans-serif, system-ui`;
          ctx.fillStyle = n.type === "concept" ? "rgba(170,180,205,0.85)" : "rgba(228,232,245,0.92)";
          ctx.textAlign = "center";
          ctx.fillText(n.label.slice(0, 34), n.x, n.y + n.r + 11 / s.view.scale);
        }
        ctx.globalAlpha = 1;
      }
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      if (!disposed) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    // ── Pointer interactions ──
    const onDown = (ev: PointerEvent) => {
      const s = sim.current; if (!s) return;
      canvas.setPointerCapture(ev.pointerId);
      const n = hit(ev.clientX, ev.clientY);
      if (n) { s.dragging = n; n.fixed = true; s.alpha = Math.max(s.alpha, 0.35); }
      else s.panning = true;
      s.last = { x: ev.clientX, y: ev.clientY };
    };
    const onMove = (ev: PointerEvent) => {
      const s = sim.current; if (!s) return;
      if (s.dragging) {
        const w = toWorld(ev.clientX, ev.clientY);
        s.dragging.x = w.x; s.dragging.y = w.y;
        s.dragging.vx = 0; s.dragging.vy = 0;
        s.alpha = Math.max(s.alpha, 0.25);
      } else if (s.panning) {
        s.view.x += (ev.clientX - s.last.x) / s.view.scale;
        s.view.y += (ev.clientY - s.last.y) / s.view.scale;
        s.last = { x: ev.clientX, y: ev.clientY };
      } else {
        const h = hit(ev.clientX, ev.clientY);
        s.hovered = h;
        canvas.style.cursor = h ? "pointer" : "grab";
      }
    };
    const onUp = (ev: PointerEvent) => {
      const s = sim.current; if (!s) return;
      const moved = Math.hypot(ev.clientX - s.last.x, ev.clientY - s.last.y);
      if (s.dragging) {
        s.dragging.fixed = false;
        if (moved < 4) propsRef.current.onSelect(s.dragging);
        s.dragging = null;
      } else if (s.panning && moved < 4) {
        propsRef.current.onSelect(null); // click vacío deselecciona
      }
      s.panning = false;
    };
    const onWheel = (ev: WheelEvent) => {
      const s = sim.current; if (!s) return;
      ev.preventDefault();
      const factor = Math.exp(-ev.deltaY * 0.0012);
      s.view.scale = Math.min(4, Math.max(0.25, s.view.scale * factor));
    };
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("wheel", onWheel);
    };
  }, []);

  return <canvas ref={canvasRef} className="w-full h-full rounded-xl" style={{ touchAction: "none" }} />;
}
