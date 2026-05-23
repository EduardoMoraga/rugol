"""Import a Moragent project's .claude/ folder into this Rogologo install."""
from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Op:
    kind: str
    src: Path
    dst: Path
    action: str


def collect(source: Path, dest: Path, overwrite: bool) -> list[Op]:
    src_claude = source / ".claude"
    if not src_claude.is_dir():
        sys.exit(f"ERROR: {source} does not contain a .claude/ directory.")

    ops: list[Op] = []

    file_kinds = {
        "agent": (src_claude / "agents", dest / "agents"),
        "skill": (src_claude / "skills", dest / "skills"),
    }
    for kind, (src_dir, dst_dir) in file_kinds.items():
        if not src_dir.is_dir():
            continue
        for f in sorted(src_dir.glob("*.md")):
            target = dst_dir / f.name
            if target.exists():
                action = "overwrite" if overwrite else "skip"
            else:
                action = "copy"
            ops.append(Op(kind, f, target, action))

    mem_src = src_claude / "agent-memory"
    if mem_src.is_dir():
        for entry in sorted(mem_src.iterdir()):
            if not entry.is_dir():
                continue
            target_dir = dest / "agent-memory" / entry.name
            if target_dir.exists():
                action = "overwrite" if overwrite else "skip"
            else:
                action = "copy"
            ops.append(Op("memory", entry, target_dir, action))

    return ops


def report(ops: list[Op]) -> None:
    print()
    print(f"{'KIND':<8} {'ACTION':<10} {'NAME':<40} TARGET")
    print("-" * 90)
    for op in ops:
        try:
            rel = op.dst.relative_to(ROOT)
        except ValueError:
            rel = op.dst
        print(f"{op.kind:<8} {op.action:<10} {op.src.name:<40} {rel}")

    counts: dict[str, dict[str, int]] = {}
    for op in ops:
        counts.setdefault(op.kind, {}).setdefault(op.action, 0)
        counts[op.kind][op.action] += 1

    plural = {"agent": "agents", "skill": "skills", "memory": "memories"}
    print()
    for kind, by_action in sorted(counts.items()):
        parts = ", ".join(f"{a}={n}" for a, n in sorted(by_action.items()))
        print(f"  {plural.get(kind, kind + 's')}: {parts}")
    print()


def apply(ops: list[Op]) -> int:
    written = 0
    for op in ops:
        if op.action == "skip":
            continue
        op.dst.parent.mkdir(parents=True, exist_ok=True)
        if op.dst.exists():
            if op.dst.is_dir():
                shutil.rmtree(op.dst)
            else:
                op.dst.unlink()
        if op.src.is_dir():
            shutil.copytree(op.src, op.dst)
        else:
            shutil.copy2(op.src, op.dst)
        written += 1
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, type=Path,
                    help="Path to the Moragent project (folder containing .claude/)")
    ap.add_argument("--dest", type=Path, default=ROOT,
                    help="Rogologo install root (default: auto-detected)")
    ap.add_argument("--apply", action="store_true",
                    help="Actually perform the copy (default is dry-run)")
    ap.add_argument("--overwrite", action="store_true",
                    help="Replace files that already exist in destination")
    args = ap.parse_args()

    source = args.source.resolve()
    dest = args.dest.resolve()

    if not source.is_dir():
        sys.exit(f"ERROR: source {source} is not a directory.")
    if not dest.is_dir():
        sys.exit(f"ERROR: dest {dest} is not a directory.")

    print(f"Source: {source}")
    print(f"Dest:   {dest}")
    print(f"Mode:   {'APPLY' if args.apply else 'DRY-RUN (use --apply to copy)'}")
    print(f"Conflict policy: {'overwrite' if args.overwrite else 'skip'}")

    ops = collect(source, dest, args.overwrite)
    if not ops:
        print("\nNothing to import — source has no agents, skills, or memory.")
        return

    report(ops)

    if not args.apply:
        print("Dry-run only. Re-run with --apply to perform the copy.")
        return

    written = apply(ops)
    print(f"Wrote {written} item(s). The watcher will register them within DISCOVERY_INTERVAL seconds.")


if __name__ == "__main__":
    main()
