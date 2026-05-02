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
    queryFn: fetchAgents,
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

    const positions = hexLayout(merged.length, 92, size.w / 2, size.h / 2);

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

      merged.forEach((agent, i) => {
        const pos = positions[i];
        if (!pos) return;
        const color = STATE_COLOR[agent.status] ?? STATE_COLOR.idle;
        const isLive = agent.status === "running";
        const phase = (t / 600 + i * 0.7) % (Math.PI * 2);
        const wobble = isLive ? 4 : 0;
        const cx = pos.x + Math.cos(phase) * wobble;
        const cy = pos.y + Math.sin(phase) * wobble;

        // Halo
        const haloR = isLive ? 26 + Math.sin(t / 350) * 4 : 18;
        const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, haloR);
        grad.addColorStop(0, hexA(color, 0.45));
        grad.addColorStop(1, hexA(color, 0));
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, haloR, 0, Math.PI * 2);
        ctx.fill();

        // Body
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(cx, cy, 7, 0, Math.PI * 2);
        ctx.fill();

        // Inner glow
        ctx.fillStyle = "rgba(255,255,255,0.85)";
        ctx.beginPath();
        ctx.arc(cx - 1.5, cy - 1.5, 1.8, 0, Math.PI * 2);
        ctx.fill();

        // Label
        ctx.fillStyle = "rgba(244,244,245,0.65)";
        ctx.font = "11px ui-monospace, 'Geist Mono', monospace";
        ctx.textAlign = "center";
        ctx.fillText(agent.name, cx, cy + 24);
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
