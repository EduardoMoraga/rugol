"""Repara el doble-encoding (mojibake) en archivos .md de agentes y skills.

El bug: en sesiones previas, algunos archivos se generaron via PowerShell que
mandó JSON con encoding mal manejado al Architect, y los .md quedaron grabados
con bytes UTF-8 doble-encodeados. Ej: "ñ" (correctamente C3 B1 en UTF-8) quedó
como "Ã±" (C3 83 C2 B1).

La reparación es determinística: si los bytes en disco se decodifican como
UTF-8 y la cadena resultante contiene secuencias típicas de mojibake (Ã±, Ã©,
Ã³, Ã¡, Ã­, ¡, Â¿, etc.), esa cadena fue *originalmente* bytes Latin-1 que
representaban bytes UTF-8. La cadena "limpia" se recupera con:

    clean = corrupted.encode("latin-1").decode("utf-8")

Idempotente: archivos sin mojibake quedan intactos. Si la "reparación"
produce error de decode, se asume que el archivo ya estaba bien.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


# Marcadores típicos de mojibake — al menos uno tiene que aparecer para
# considerar reparar el archivo. Lista pequeña porque false-positives sobre
# archivos correctos son peores que dejar mojibake.
MOJIBAKE_MARKERS = ("Ã±", "Ã©", "Ã³", "Ã¡", "Ã­", "Ã¼", "Ãº", "Ã‘", "Â¡", "Â¿", "Ã§")


def looks_like_mojibake(text: str) -> bool:
    return any(m in text for m in MOJIBAKE_MARKERS)


def try_repair(text: str) -> str | None:
    """Intenta el round-trip latin-1 → utf-8. Retorna None si no aplica."""
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None
    # La reparación es válida si elimina los marcadores Y el contenido cambió.
    if repaired == text:
        return None
    if looks_like_mojibake(repaired):
        # La cadena reparada todavía tiene mojibake → el archivo está
        # triple-encodeado o algo más raro. No tocamos.
        return None
    return repaired


def repair_file(path: Path, write: bool) -> str:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return f"SKIP {path.name}: not valid UTF-8"
    if not looks_like_mojibake(text):
        return f"OK   {path.name}: clean"
    repaired = try_repair(text)
    if repaired is None:
        return f"WARN {path.name}: looks corrupted but repair did not apply"
    if write:
        path.write_text(repaired, encoding="utf-8", newline="")
        return f"FIX  {path.name}: repaired ({len(text)} -> {len(repaired)} chars)"
    return f"DRY  {path.name}: WOULD repair ({len(text)} -> {len(repaired)} chars)"


def main() -> int:
    ap = argparse.ArgumentParser(description="Repara mojibake en archivos .md")
    ap.add_argument("dirs", nargs="+", help="Directorios a recorrer")
    ap.add_argument("--write", action="store_true", help="Aplicar cambios (por defecto: dry-run)")
    args = ap.parse_args()

    fixed = 0
    seen = 0
    for d in args.dirs:
        for path in Path(d).rglob("*.md"):
            seen += 1
            result = repair_file(path, write=args.write)
            print(result)
            if result.startswith(("FIX ", "DRY ")):
                fixed += 1
    mode = "fixed" if args.write else "would fix"
    print(f"\n{seen} files scanned · {fixed} {mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
