"use client";

import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  MiniMap,
  Node,
  NodeProps,
  Handle,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";
import type { OntologyEdge, OntologyNode } from "@/lib/api";

const TYPE_COLOR: Record<string, string> = {
  concept: "var(--color-accent)",
  entity: "#60a5fa",
  event: "#f59e0b",
};

function OntologyNodeView({ data }: NodeProps<{ label: string; type: string }>) {
  const color = TYPE_COLOR[data.type] ?? "var(--color-fg-muted)";
  return (
    <div
      className="rounded-md border bg-[--color-bg-elev] px-3 py-2 text-xs font-mono shadow-md"
      style={{ borderColor: color, minWidth: 120 }}
    >
      <Handle type="target" position={Position.Left} style={{ background: color }} />
      <div className="text-[10px] uppercase tracking-wider" style={{ color }}>{data.type}</div>
      <div className="text-[--color-fg]">{data.label}</div>
      <Handle type="source" position={Position.Right} style={{ background: color }} />
    </div>
  );
}

const nodeTypes = { ontology: OntologyNodeView };

interface Props {
  nodes: OntologyNode[];
  edges: OntologyEdge[];
}

export function OntologyGraph({ nodes, edges }: Props) {
  const flowNodes: Node[] = useMemo(() => {
    if (nodes.length === 0) return [];
    // Circular layout: stable, scales gracefully up to a few hundred nodes.
    const radius = Math.max(220, nodes.length * 18);
    return nodes.map((n, i) => {
      const theta = (i / nodes.length) * Math.PI * 2;
      return {
        id: String(n.id),
        type: "ontology",
        position: { x: Math.cos(theta) * radius, y: Math.sin(theta) * radius },
        data: { label: n.label, type: n.type },
      };
    });
  }, [nodes]);

  const flowEdges: Edge[] = useMemo(
    () =>
      edges.map((e) => ({
        id: `e${e.id}`,
        source: String(e.src),
        target: String(e.dst),
        label: e.predicate,
        labelStyle: { fontSize: 10, fontFamily: "monospace", fill: "var(--color-fg-muted)" },
        labelBgStyle: { fill: "var(--color-bg)" },
        style: { stroke: "var(--color-border)", strokeWidth: 1.5 },
        animated: false,
      })),
    [edges],
  );

  return (
    <div className="w-full h-[640px] card p-0 overflow-hidden">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#262626" gap={20} />
        <Controls className="!bg-[--color-bg-elev] !border-[--color-border]" />
        <MiniMap
          className="!bg-[--color-bg-elev] !border-[--color-border]"
          nodeColor={(n) => TYPE_COLOR[(n.data as any)?.type] ?? "#71717a"}
          maskColor="rgba(0,0,0,0.6)"
        />
      </ReactFlow>
    </div>
  );
}
