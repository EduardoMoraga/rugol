"use client";

import { useState } from "react";
import { Wrench, Eye, Plus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { fetchSkills, fetchSkillSource, type Skill } from "@/lib/api";
import { Card, PageHeader } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export default function SkillsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["skills"], queryFn: fetchSkills });
  const total = data?.length ?? 0;

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      <PageHeader
        title="Skills"
        description="Reusable capabilities discovered from your SKILLS_DIR. Architect proposes new skills as part of a deploy; you can also drop .md files directly into the folder."
        actions={
          <span className="text-xs text-[--color-fg-muted]">{total} registered</span>
        }
      />

      {isLoading && <p className="text-sm text-[--color-fg-muted]">Loading…</p>}

      {data && data.length === 0 && (
        <Card className="text-center py-10 space-y-3">
          <Wrench size={28} className="mx-auto text-[--color-accent-strong]" />
          <h2 className="text-lg font-semibold">No skills yet</h2>
          <p className="text-sm text-[--color-fg-muted] max-w-md mx-auto">
            Skills are reusable instructions any agent can invoke. Run Architect with an idea
            that benefits from a shared capability — it'll propose skills alongside the agents.
          </p>
        </Card>
      )}

      {data && data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {data.map((s) => (
            <SkillCard key={s.id} skill={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function SkillCard({ skill }: { skill: Skill }) {
  return (
    <Card className="space-y-2">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold tracking-tight">{skill.name}</h3>
          {skill.description && (
            <p className="text-xs text-[--color-fg-muted] mt-1">{skill.description}</p>
          )}
        </div>
        <SourceDialog skillId={skill.id} skillName={skill.name} />
      </header>
      <p className="text-[11px] font-mono text-[--color-fg-subtle] truncate">{skill.source_path}</p>
    </Card>
  );
}

function SourceDialog({ skillId, skillName }: { skillId: number; skillName: string }) {
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["skill-source", skillId],
    queryFn: () => fetchSkillSource(skillId),
    enabled: open,
  });
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm">
          <Eye size={12} /> View
        </Button>
      </DialogTrigger>
      <DialogContent
        title={skillName}
        description={data?.description}
        className="max-w-3xl"
      >
        {isLoading || !data ? (
          <p className="text-sm text-[--color-fg-muted]">Loading…</p>
        ) : (
          <pre className="text-[12px] whitespace-pre-wrap font-mono text-[--color-fg-muted] leading-relaxed bg-[--color-bg] p-4 rounded-md border border-[--color-border] max-h-[480px] overflow-y-auto">
            {data.body}
          </pre>
        )}
      </DialogContent>
    </Dialog>
  );
}
