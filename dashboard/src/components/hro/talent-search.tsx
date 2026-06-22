"use client";

/**
 * TalentSearch — buscador interno / recomendación sobre el pipeline vivo.
 *
 * La reclutadora escribe qué busca ("promotor retail con experiencia en
 * terreno") y el banco de talento rankea a los candidatos por su última
 * entrevista (BARS) + score de screening. Reaprovecha candidatos calificados,
 * también para vacantes que recién surgen. Reusa GET /api/pipeline/recommend.
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search, Trophy } from "lucide-react";
import { recommendCandidates } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toast";
import { useI18n } from "@/lib/i18n";

export function TalentSearch() {
  const { t } = useI18n();
  const [q, setQ] = useState("");

  const search = useMutation({
    mutationFn: () => recommendCandidates(q.trim(), { limit: 5 }),
    onError: (e: Error) => toast({ tone: "error", title: t("talent.error"), body: e.message }),
  });
  const results = search.data ?? [];

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <Trophy size={16} className="text-[--color-accent-strong]" />
        <h2 className="text-sm font-semibold tracking-tight">{t("talent.title")}</h2>
      </div>
      <p className="text-[12.5px] text-[--color-fg-muted] leading-relaxed max-w-3xl -mt-1">
        {t("talent.subtitle")}
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) search.mutate();
        }}
        className="flex items-center gap-2"
      >
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("talent.placeholder")}
        />
        <Button type="submit" variant="primary" disabled={!q.trim() || search.isPending}>
          <Search size={14} /> {search.isPending ? t("talent.searching") : t("talent.search")}
        </Button>
      </form>

      {search.isSuccess && (
        results.length === 0 ? (
          <p className="text-[13px] text-[--color-fg-muted]">{t("talent.empty")}</p>
        ) : (
          <ol className="space-y-2">
            {results.map((c, i) => (
              <li key={c.id} className="surface px-3 py-2.5 flex items-center gap-3">
                <span className="w-6 h-6 rounded-full grid place-items-center shrink-0 bg-[--color-accent-soft] text-[--color-accent-strong] text-[11px] font-semibold tabular-nums">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-medium truncate">{c.title}</p>
                  <p className="text-[11.5px] text-[--color-fg-muted] truncate">
                    {c.why || c.subtitle || "—"}
                  </p>
                </div>
                {typeof c.score === "number" && (
                  <Badge tone={c.score >= 4 ? "running" : c.score >= 3 ? "accent" : "idle"} className="shrink-0 text-[10px] tabular-nums">
                    {c.score}/5
                  </Badge>
                )}
              </li>
            ))}
          </ol>
        )
      )}
    </section>
  );
}
