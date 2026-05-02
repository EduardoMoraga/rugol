import Link from "next/link";

interface Props {
  title: string;
  body: string;
  ctaLabel?: string;
  ctaHref?: string;
}

export function EmptyState({ title, body, ctaLabel, ctaHref }: Props) {
  return (
    <div className="card border-dashed text-center py-12 px-6">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="text-sm text-[--color-fg-muted] mt-2 max-w-md mx-auto">{body}</p>
      {ctaLabel && ctaHref && (
        <Link
          href={ctaHref}
          className="inline-block mt-4 px-3 py-1.5 text-sm rounded border border-[--color-border] hover:bg-[--color-border] transition"
        >
          {ctaLabel}
        </Link>
      )}
    </div>
  );
}
