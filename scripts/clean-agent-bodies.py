"""Detect and clean stale integration restrictions in agent bodies.

When the Architect deploys agents in v0.5 it sometimes injected sentences
like "sin YouTube API por ahora" or "until Gmail is connected" into the
permanent body of each agent. Once the integration gets wired (MCP server
configured), the body still says it's missing — the model trusts the body
and ignores the new tool.

This script finds those sentences and offers to remove them surgically.

Usage
-----
    # Dry run — list problematic lines, do not write
    python scripts/clean-agent-bodies.py

    # Specify a different agents directory
    python scripts/clean-agent-bodies.py --dir ./my-agents

    # Apply the cleanups (rewrites the .md files)
    python scripts/clean-agent-bodies.py --apply

    # Verbose — show diff per file
    python scripts/clean-agent-bodies.py --verbose
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Patterns that flag stale "this integration is not available yet" sentences.
# Each is a regex applied per-line (case-insensitive). Add more as we see them
# in the wild — the goal is high precision, not recall: false positives here
# would silently mutilate good agent bodies.
STALE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "yt-no-api",
        re.compile(
            r"sin\s+(integraci[oó]n(es)?\s+directa(s)?\s+a\s+)?youtube\s+api",
            re.IGNORECASE,
        ),
    ),
    (
        "yt-fallback",
        re.compile(
            r"trabaja\s+con\s+lo\s+que\s+puedas\s+recuperar\s+v[ií]a\s+b[uú]squeda\s+web",
            re.IGNORECASE,
        ),
    ),
    (
        "gmail-pending",
        re.compile(
            r"(hasta|until)\s+(que\s+)?gmail\s+(est[eé]|is|gets?)\s+(conectado|connected|wired)",
            re.IGNORECASE,
        ),
    ),
    (
        "calendar-pending",
        re.compile(
            r"(hasta|until)\s+(que\s+)?(google\s+)?calendar\s+(est[eé]|is|gets?)\s+(conectado|connected|wired)",
            re.IGNORECASE,
        ),
    ),
    (
        "asana-pending",
        re.compile(
            r"sin\s+integraci[oó]n(es)?\s+directa(s)?\s+a\s+asana",
            re.IGNORECASE,
        ),
    ),
    (
        "for-now",
        re.compile(
            r"(por\s+ahora|for\s+now|until\s+it'?s?\s+(connected|wired))",
            re.IGNORECASE,
        ),
    ),
]


def find_stale_lines(text: str) -> list[tuple[int, str, list[str]]]:
    """Return [(line_number_1based, line_text, [pattern_ids_that_matched])]."""
    hits: list[tuple[int, str, list[str]]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        matched = [pid for pid, pat in STALE_PATTERNS if pat.search(line)]
        if matched:
            hits.append((idx, line, matched))
    return hits


def clean(text: str) -> str:
    """Remove every line that matches any stale pattern. Preserve everything else."""
    out_lines: list[str] = []
    for line in text.splitlines():
        if any(pat.search(line) for _, pat in STALE_PATTERNS):
            continue
        out_lines.append(line)
    # Preserve trailing newline if original had one.
    if text.endswith("\n"):
        return "\n".join(out_lines) + "\n"
    return "\n".join(out_lines)


def process(path: Path, *, apply: bool, verbose: bool) -> int:
    """Returns count of stale lines found in this file."""
    text = path.read_text(encoding="utf-8")
    hits = find_stale_lines(text)
    if not hits:
        return 0
    print(f"\n[{path.name}] {len(hits)} stale line(s):")
    for line_no, line, matched in hits:
        markers = ", ".join(matched)
        print(f"  line {line_no} [{markers}]: {line.strip()}")
    if apply:
        cleaned = clean(text)
        if verbose:
            print("--- new content ---")
            print(cleaned)
            print("--- end ---")
        path.write_text(cleaned, encoding="utf-8")
        print(f"  -> rewrote {path}")
    return len(hits)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        default="agents",
        help="Directory of agent .md files (default: ./agents)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rewrite files (default: dry-run, only report)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="When applying, print the cleaned body of each file",
    )
    args = parser.parse_args()

    base = Path(args.dir)
    if not base.exists():
        print(f"Directory not found: {base.resolve()}", file=sys.stderr)
        return 2

    md_files = sorted(base.glob("*.md"))
    if not md_files:
        print(f"No .md files in {base.resolve()}")
        return 0

    total_hits = 0
    files_with_hits = 0
    for path in md_files:
        n = process(path, apply=args.apply, verbose=args.verbose)
        total_hits += n
        if n:
            files_with_hits += 1

    print(
        f"\nDone. Files inspected: {len(md_files)}. "
        f"Files with stale lines: {files_with_hits}. "
        f"Total stale lines: {total_hits}."
    )
    if total_hits and not args.apply:
        print("\nThis was a dry run. Re-run with --apply to remove the lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
