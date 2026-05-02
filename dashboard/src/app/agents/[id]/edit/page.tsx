"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AgentForm } from "@/components/agents/agent-form";
import { fetchAgentSource, updateAgent, type AgentSpec } from "@/lib/api";

export default function EditAgentPage() {
  const params = useParams<{ id: string }>();
  const agentId = Number(params.id);

  const { data, isLoading } = useQuery({
    queryKey: ["agent-source", agentId],
    queryFn: () => fetchAgentSource(agentId),
    enabled: !Number.isNaN(agentId),
  });

  if (isLoading || !data) {
    return <p className="p-8 text-sm text-[--color-fg-muted]">Loading spec…</p>;
  }

  return (
    <AgentForm
      mode="edit"
      title={`Edit ${data.name}`}
      description={`Source: ${data.source_path}`}
      initial={{
        name: data.name,
        model: data.model,
        description: data.description,
        body: data.body,
      }}
      onSubmit={(spec: AgentSpec) => updateAgent(agentId, spec)}
      redirectTo={(id) => `/agents/${id}`}
    />
  );
}
