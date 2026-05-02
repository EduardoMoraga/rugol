"use client";

import { Application, extend } from "@pixi/react";
import { Container, Graphics, Text } from "pixi.js";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAgents, type Agent } from "@/lib/api";
import { useStream } from "@/lib/use-stream";

extend({ Container, Graphics, Text });

interface Pos { x: number; y: number; }

function hexLayout(n: number, radius = 80, centerX = 0, centerY = 0): Pos[] {
  // Rings of hexagonal positions: 1 + 6 + 12 + 18 + ...
  const positions: Pos[] = [{ x: centerX, y: centerY }];
  let ring = 1;
  while (positions.length < n) {
    const count = ring * 6;
    for (let i = 0; i < count && positions.length < n; i++) {
      const angle = (i / count) * Math.PI * 2;
      positions.push({
        x: centerX + Math.cos(angle) * radius * ring,
        y: centerY + Math.sin(angle) * radius * ring,
      });
    }
    ring++;
  }
  return positions;
}

const STATE_COLOR: Record<string, number> = {
  idle: 0x71717a,
  running: 0x84cc16,
  error: 0xef4444,
  offline: 0x3f3f46,
};

interface AntProps {
  agent: Agent;
  pos: Pos;
  jitter: number;
}

function Ant({ agent, pos, jitter }: AntProps) {
  const [phase, setPhase] = useState(0);
  useEffect(() => {
    if (agent.status !== "running") return;
    const t = setInterval(() => setPhase((p) => (p + 1) % 8), 120);
    return () => clearInterval(t);
  }, [agent.status]);

  const wobbleX = agent.status === "running" ? Math.cos(phase) * 6 : 0;
  const wobbleY = agent.status === "running" ? Math.sin(phase) * 6 : 0;
  const color = STATE_COLOR[agent.status] ?? 0x71717a;

  const draw = useCallback((g: Graphics) => {
    g.clear();
    // body
    g.circle(0, 0, 10).fill(color);
    g.circle(-9, 0, 6).fill(color);
    g.circle(9, 0, 6).fill(color);
    // legs
    g.stroke({ width: 1.5, color });
    [-1, 0, 1].forEach((s) => {
      g.moveTo(0, -2 + s * 2).lineTo(-15, -10 + s * 6);
      g.moveTo(0, -2 + s * 2).lineTo(15, -10 + s * 6);
    });
    // antennae
    g.moveTo(-7, -4).lineTo(-12, -14);
    g.moveTo(7, -4).lineTo(12, -14);
    g.stroke();
    if (agent.status === "error") {
      g.circle(0, -22, 4).fill(0xef4444);
    }
  }, [color, agent.status]);

  return (
    <pixiContainer x={pos.x + wobbleX + jitter} y={pos.y + wobbleY + jitter}>
      <pixiGraphics draw={draw} />
      <pixiText
        text={agent.name}
        x={0}
        y={22}
        anchor={{ x: 0.5, y: 0 }}
        style={{ fill: 0xa1a1aa, fontSize: 10, fontFamily: "monospace" }}
      />
    </pixiContainer>
  );
}

export function AntFarmCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 600, h: 400 });
  const agents = useQuery({
    queryKey: ["agents-farm"],
    queryFn: fetchAgents,
    refetchInterval: 4000,
  });

  // Live status updates from SSE
  const [statusOverride, setStatusOverride] = useState<Record<string, Agent["status"]>>({});
  useStream("run:*", (e) => {
    const name = e.data?.agent;
    if (!name) return;
    if (e.topic === "run:started") setStatusOverride((s) => ({ ...s, [name]: "running" }));
    if (e.topic === "run:completed") setStatusOverride((s) => ({ ...s, [name]: "idle" }));
    if (e.topic === "run:failed") setStatusOverride((s) => ({ ...s, [name]: "error" }));
  });

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver((entries) => {
      const r = entries[0].contentRect;
      setSize({ w: Math.max(200, r.width), h: Math.max(200, r.height) });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  const positions = useMemo(
    () => hexLayout(agents.data?.length ?? 0, 90, size.w / 2, size.h / 2),
    [agents.data, size],
  );

  return (
    <div ref={containerRef} className="w-full h-full bg-black/40">
      <Application width={size.w} height={size.h} background={0x0a0a0a} antialias>
        {agents.data?.map((a, i) => {
          const status = statusOverride[a.name] ?? a.status;
          return <Ant key={a.id} agent={{ ...a, status }} pos={positions[i] ?? { x: 0, y: 0 }} jitter={(i % 3) * 2} />;
        })}
      </Application>
    </div>
  );
}
