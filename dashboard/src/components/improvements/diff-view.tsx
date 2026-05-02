"use client";

interface Props {
  diff: string;
}

export function DiffView({ diff }: Props) {
  const lines = diff.split("\n");
  return (
    <pre className="text-xs bg-black/50 p-3 rounded overflow-x-auto leading-relaxed font-mono">
      {lines.map((line, i) => {
        const role = classify(line);
        return (
          <div key={i} className={cls(role)}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}

type Role = "add" | "del" | "hunk" | "header" | "context";

function classify(line: string): Role {
  if (line.startsWith("+++") || line.startsWith("---")) return "header";
  if (line.startsWith("+")) return "add";
  if (line.startsWith("-")) return "del";
  if (line.startsWith("@@")) return "hunk";
  return "context";
}

function cls(role: Role): string {
  switch (role) {
    case "add":
      return "text-[--color-accent] bg-[--color-accent]/10";
    case "del":
      return "text-[--color-error] bg-[--color-error]/10";
    case "hunk":
      return "text-[--color-warn]";
    case "header":
      return "text-[--color-fg-muted] font-semibold";
    default:
      return "text-[--color-fg-muted]";
  }
}
