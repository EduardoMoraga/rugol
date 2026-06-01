"use client";

import { AgentForm } from "@/components/agents/agent-form";
import { createAgent } from "@/lib/api";

export default function NewAgentPage() {
  return (
    <AgentForm
      mode="create"
      title="New agent"
      description="Define the spec; Rugol writes the markdown to your agents folder and registers it."
      onSubmit={createAgent}
      redirectTo={(id) => `/agents/${id}`}
    />
  );
}
