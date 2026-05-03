"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAgents, type Agent } from "@/lib/api";
import { useStream } from "@/lib/use-stream";

const STATE_COLOR: Record<string, string> = {
  idle: "#6b7280",
  running: "#4ade80",
  error: "#f87171",
  offline: "#3f3f46",
};

interface Pos { x: number; y: number; }

function hexLayout(n: number, radius: number, cx: number, cy: number): Pos[] {
  if (n <= 0) return [];
  const positions: Pos[] = [{ x: cx, y: cy }];
  let ring = 1;
  while (positions.length < n) {
    const count = ring * 6;
    for (let i = 0; i < count && positions.length < n; i++) {
      const angle = (i / count) * Math.PI * 2;
      positions.push({
        x: cx + Math.cos(angle) * radius * ring,
        y: cy + Math.sin(angle) * radius * ring,
      });
    }
    ring++;
  }
  return positions;
}

/**
 * Plain HTML5 canvas. No WebGL, no react-pixi, no context loss. Each agent
 * is drawn as a soft halo + dot + label; running agents wobble + pulse.
 */
export function AntFarmCanvas() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ w: 600, h: 400 });

  const agents = useQuery({
    queryKey: ["agents-farm"],
    queryFn: () => fetchAgents(),
    refetchInterval: 4000,
  });

  // SSE-driven status overrides keyed by agent name.
  const [overrides, setOverrides] = useState<Record<string, Agent["status"]>>({});
  useStream("run:*", (e) => {
    const name = e.data?.agent;
    if (!name) return;
    setOverrides((s) => {
      if (e.topic === "run:started") return { ...s, [name]: "running" };
      if (e.topic === "run:completed") return { ...s, [name]: "idle" };
      if (e.topic === "run:failed") return { ...s, [name]: "error" };
      return s;
    });
  });

  const merged: Agent[] = useMemo(
    () =>
      (agents.data ?? []).map((a) => ({
        ...a,
        status: overrides[a.name] ?? a.status,
      })),
    [agents.data, overrides],
  );

  // Resize observer.
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const r = entries[0].contentRect;
      setSize({ w: Math.max(280, Math.floor(r.width)), h: Math.max(280, Math.floor(r.height)) });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Animation loop.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
    canvas.width = size.w * dpr;
    canvas.height = size.h * dpr;
    canvas.style.width = `${size.w}px`;
    canvas.style.height = `${size.h}px`;
    ctx.scale(dpr, dpr);

    let raf = 0;
    let alive = true;

    // Capa 9: cluster agents by project. Each cluster gets a center point
    // on a hex grid; its agents orbit that center. Visually you see your
    // departments as constellations, not a uniform soup of dots.
    type Cluster = {
      slug: string;
      name: string;
      color: string;
      center: Pos;
      agents: Agent[];
    };
    const grouped = new Map<string, Cluster>();
    merged.forEach((a) => {
      const slug = a.project_slug || "_orphan";
      let c = grouped.get(slug);
      if (!c) {
        c = {
          slug,
          name: a.project_name || "Workspace",
          color: a.project_color || "#7280a8",
          center: { x: 0, y: 0 },
          agents: [],
        };
        grouped.set(slug, c);
      }
      c.agents.push(a);
    });
    const clusters = Array.from(grouped.values());
    const clusterCenters = hexLayout(
      clusters.length,
      Math.min(size.w, size.h) * 0.32,
      size.w / 2,
      size.h / 2,
    );
    clusters.forEach((c, i) => {
      c.center = clusterCenters[i] ?? { x: size.w / 2, y: size.h / 2 };
    });

    function draw(t: number) {
      if (!alive || !ctx) return;
      ctx.clearRect(0, 0, size.w, size.h);

      // Subtle grid in the background.
      ctx.strokeStyle = "rgba(255,255,255,0.025)";
      ctx.lineWidth = 1;
      for (let x = 0; x < size.w; x += 32) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, size.h);
        ctx.stroke();
      }
      for (let y = 0; y < size.h; y += 32) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(size.w, y);
        ctx.stroke();
      }

      // Per-cluster: draw the project halo (color), the connector lines,
      // and the cluster label first so dots stack on top.
      clusters.forEach((c) => {
        const orbitR = Math.max(38, 16 + c.agents.length * 10);
        // Project tint background.
        const haloGrad = ctx.createRadialGradient(c.center.x, c.center.y, 4, c.center.x, c.center.y, orbitR + 28);
        haloGrad.addColorStop(0, hexA(c.color, 0.16));
        haloGrad.addColorStop(1, hexA(c.color, 0));
        ctx.fillStyle = haloGrad;
        ctx.beginPath();
        ctx.arc(c.center.x, c.center.y, orbitR + 28, 0, Math.PI * 2);
        ctx.fill();

        // Connector lines — only between members of the same cluster, faint.
        if (c.agents.length > 1) {
          ctx.strokeStyle = hexA(c.color, 0.18);
          ctx.lineWidth = 1;
          c.agents.forEach((_, i) => {
            const angleA = (i / c.agents.length) * Math.PI * 2 + (t / 8000);
            const ax = c.center.x + Math.cos(angleA) * orbitR;
            const ay = c.center.y + Math.sin(angleA) * orbitR;
            const next = (i + 1) % c.agents.length;
            const angleB = (next / c.agents.length) * Math.PI * 2 + (t / 8000);
            const bx = c.center.x + Math.cos(angleB) * orbitR;
            const by = c.center.y + Math.sin(angleB) * orbitR;
            ctx.beginPath();
            ctx.moveTo(ax, ay);
            ctx.lineTo(bx, by);
            ctx.stroke();
          });
        }

        // Cluster label.
        ctx.fillStyle = hexA(c.color, 0.85);
        ctx.font = "600 12px ui-sans-serif, system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(c.name.toUpperCase(), c.center.x, c.center.y - orbitR - 14);
        ctx.fillStyle = "rgba(244,244,245,0.4)";
        ctx.font = "10px ui-monospace, 'Geist Mono', monospace";
        ctx.fillText(`${c.agents.length} agente${c.agents.length === 1 ? "" : "s"}`, c.center.x, c.center.y - orbitR - 1);
      });

      // Now draw agents on top, orbiting their cluster center.
      clusters.forEach((c) => {
        const orbitR = Math.max(38, 16 + c.agents.length * 10);
        c.agents.forEach((agent, i) => {
          const stateColor = STATE_COLOR[agent.status] ?? STATE_COLOR.idle;
          const isLive = agent.status === "running";
          const angle = (i / c.agents.length) * Math.PI * 2 + (t / 8000);
          const cx = c.center.x + Math.cos(angle) * orbitR;
          const cy = c.center.y + Math.sin(angle) * orbitR;

          // Project-tinted halo.
          const haloR = isLive ? 22 + Math.sin(t / 350) * 4 : 14;
          const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, haloR);
          grad.addColorStop(0, hexA(c.color, 0.55));
          grad.addColorStop(1, hexA(c.color, 0));
          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.arc(cx, cy, haloR, 0, Math.PI * 2);
          ctx.fill();

          // Body — color reflects RUN STATUS (so live runs visibly pulse green
          // even inside a project's tint).
          ctx.fillStyle = stateColor;
          ctx.beginPath();
          ctx.arc(cx, cy, 6, 0, Math.PI * 2);
          ctx.fill();

          // Inner glow.
          ctx.fillStyle = "rgba(255,255,255,0.85)";
          ctx.beginPath();
          ctx.arc(cx - 1.2, cy - 1.2, 1.5, 0, Math.PI * 2);
          ctx.fill();

          // Agent label.
          ctx.fillStyle = "rgba(244,244,245,0.7)";
          ctx.font = "10.5px ui-monospace, 'Geist Mono', monospace";
          ctx.textAlign = "center";
          ctx.fillText(agent.name, cx, cy + 20);
        });
      });

      raf = requestAnimationFrame(draw);
    }

    raf = requestAnimationFrame(draw);
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      // Reset transform so next mount re-applies the dpr scale on a fresh canvas.
      ctx.setTransform(1, 0, 0, 1, 0, 0);
    };
  }, [merged, size]);

  return (
    <div ref={wrapperRef} className="w-full h-full relative bg-[--color-bg]">
      <canvas ref={canvasRef} />
      {merged.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-[--color-fg-muted]">
          No agents registered yet.
        </div>
      )}
    </div>
  );
}

function hexA(hex: string, alpha: number): string {
  // Accepts #rgb / #rrggbb / fallback to passthrough.
  const m = hex.replace("#", "");
  if (m.length === 3) {
    const r = parseInt(m[0] + m[0], 16);
    const g = parseInt(m[1] + m[1], 16);
    const b = parseInt(m[2] + m[2], 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }
  if (m.length === 6) {
    const r = parseInt(m.slice(0, 2), 16);
    const g = parseInt(m.slice(2, 4), 16);
    const b = parseInt(m.slice(4, 6), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }
  return hex;
}
