#!/usr/bin/env python3
"""batch_analyze_presets.py - hromadna analyza preset indexu pro feature vektory.

Cte data/presets/index/*.jsonl a pro kazdy preset:
1. Nacte plny dump z data/presets/_local/<pack>/<id>.json
2. Spusti analyze_preset.py analyzu
3. Ulozi feature vektor + analyzu do data/presets/analyzed/<id>.json

Pouziti:
  python tools/batch_analyze_presets.py                    # zpracuje vsechny indexy
  python tools/batch_analyze_presets.py --source-id pythius-patreon-presets
  python tools/batch_analyze_presets.py --dry-run          # jen zobrazí co by se zpracovalo
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import analyze_preset as ap  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = REPO_ROOT / "data" / "presets" / "index"
LOCAL_DIR = REPO_ROOT / "data" / "presets" / "_local"
OUT_DIR = REPO_ROOT / "data" / "presets" / "analyzed"

PACK_MAP = {
    "enta-serum-presets": "enta-serum-presets",
    "letsynthesize-preset-files": "letsynthesize",
    "notequal-serum-presets": "notequal-serum-presets",
    "pythius-patreon-presets": "pythius-patreon-presets",
    "redpill-serum-presets": "redpill-serum-presets",
    "serum-user-folder-presets": "serum-user-folder-presets",
}


def find_index_files(source_id: str | None = None) -> list[Path]:
    """Najde index soubory k zpracovani."""
    if not INDEX_DIR.exists():
        return []
    files = sorted(INDEX_DIR.glob("*.jsonl"))
    if source_id:
        files = [f for f in files if source_id in f.stem]
    return files


def load_index(file: Path) -> list[dict]:
    """Nacte index soubor (JSONL)."""
    with file.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def analyze_all(dry_run: bool = False, source_id: str | None = None) -> None:
    index_files = find_index_files(source_id)
    if not index_files:
        print(f"Zadne index soubory nenalezeny{f' pro {source_id}' if source_id else ''}")
        return

    total = 0
    processed = 0
    errors = 0

    for idx_file in index_files:
        pack_name = idx_file.stem
        print(f"\n=== {pack_name} ===")
        presets = load_index(idx_file)
        total += len(presets)

        local_pack = PACK_MAP.get(pack_name, pack_name)

        for p in presets:
            preset_id = p["id"]
            local_file = LOCAL_DIR / local_pack / f"{preset_id}.json"
            out_file = OUT_DIR / f"{preset_id}.json"

            if not local_file.exists():
                print(f"  [WARN] {preset_id}: chybi {local_file}")
                errors += 1
                continue

            if out_file.exists() and not dry_run:
                print(f"  [SKIP] {preset_id}: uz existuje")
                continue

            print(f"  {'[DRY] ' if dry_run else ''}{preset_id}")

            if dry_run:
                continue

            try:
                            # _local soubory JUZ MAJI analyzu (jsou vystupem analyze_preset.py --dump-dir)
                            # Proste je zkopirujeme do analyzed/ s pripadnymi doplnkami
                            with local_file.open("r", encoding="utf-8") as f:
                                analysis = json.load(f)

                            # Pridame source_id a function z indexu pokud chybi
                            if "source_id" not in analysis:
                                analysis["source_id"] = p.get("source_id")
                            if "function" not in analysis:
                                analysis["function"] = p.get("function", "other")
                            if "archetype" not in analysis:
                                analysis["archetype"] = p.get("archetype", "unclassified")

                            # Uloz vysledek
                            OUT_DIR.mkdir(parents=True, exist_ok=True)
                            with out_file.open("w", encoding="utf-8") as f:
                                json.dump(analysis, f, ensure_ascii=False, indent=2)

                            processed += 1

            except Exception as e:
                print(f"  [ERROR] {preset_id}: {e}")
                errors += 1

    print(f"\n=== Souhrn ===")
    print(f"Celkem: {total}")
    print(f"Zpracovano: {processed}")
    print(f"Chyby: {errors}")
    if dry_run:
        print("(dry-run - nic se neulozilo)")


def main():
    parser = argparse.ArgumentParser(description="Batch analyza preset indexu")
    parser.add_argument("--source-id", help="Filtr podle source_id (napr. pythius-patreon-presets)")
    parser.add_argument("--dry-run", action="store_true", help="Jen zobrazi co by se zpracovalo")
    args = parser.parse_args()

    analyze_all(dry_run=args.dry_run, source_id=args.source_id)


if __name__ == "__main__":
    main()