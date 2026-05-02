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
  ReactFlowProvider,
} from "reactflow";
import "reactflow/dist/style.css";
import type { OntologyEdge, OntologyNode } from "@/lib/api";

const TYPE_COLOR: Record<string, string> = {
  concept: "#6366f1",
  entity: "#60a5fa",
  event: "#f59e0b",
};

function OntologyNodeView({ data }: NodeProps<{ label: string; type: string }>) {
  const color = TYPE_COLOR[data.type] ?? "#71717a";
  return (
    <div
      className="rounded-lg border bg-[--color-bg-elev] px-3 py-2 text-xs font-mono shadow-lg shadow-black/40"
      style={{ borderColor: color, minWidth: 140 }}
    >
      <Handle type="target" position={Position.Left} style={{ background: color, width: 8, height: 8 }} />
      <div className="text-[10px] uppercase tracking-wider font-semibold" style={{ color }}>
        {data.type}
      </div>
      <div className="text-[--color-fg] mt-0.5">{data.label}</div>
      <Handle type="source" position={Position.Right} style={{ background: color, width: 8, height: 8 }} />
    </div>
  );
}

const nodeTypes = { ontology: OntologyNodeView };

interface Props {
  nodes: OntologyNode[];
  edges: OntologyEdge[];
}

export function OntologyGraph({ nodes, edges }: Props) {
  // Hard guard: never let ReactFlow mount with zero nodes — it loops on fitView.
  if (nodes.length === 0) {
    return (
      <div className="surface h-[520px] flex items-center justify-center text-sm text-[--color-fg-muted]">
        Graph is empty.
      </div>
    );
  }

  const flowNodes: Node[] = useMemo(() => {
    const radius = Math.max(220, nodes.length * 22);
    return nodes.map((n, i) => {
      const theta = (i / Math.max(nodes.length, 1)) * Math.PI * 2;
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
        style: { stroke: "var(--color-border-strong)", strokeWidth: 1.5 },
      })),
    [edges],
  );

  return (
    <div className="surface h-[640px] p-0 overflow-hidden">
      <ReactFlowProvider>
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.25, minZoom: 0.2, maxZoom: 1.2 }}
          minZoom={0.1}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#2a2a32" gap={24} size={1.2} />
          <Controls showInteractive={false} />
          <MiniMap
            nodeColor={(n) => TYPE_COLOR[(n.data as any)?.type] ?? "#71717a"}
            maskColor="rgba(0,0,0,0.7)"
            pannable
            zoomable
          />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
