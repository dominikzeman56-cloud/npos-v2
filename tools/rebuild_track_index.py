#!/usr/bin/env python3
"""rebuild_track_index.py — z data/tracks/*/{meta,analysis}.json vygeneruje data/corpus/tracks.jsonl.

Jeden řádek na track, ploché klíče pro dotazy (bpm, tónina, crest, profil basy, modulace s basis/confidence).
Soubor se needituje ručně; spouštěj po každé nové analýze:  python tools/rebuild_track_index.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def row(meta: dict, a: dict) -> dict:
    b = a.get("bass", {})
    mod = b.get("modulation", {})
    dyn = a.get("dynamics", {})
    return {
        "id": meta["id"], "title": meta.get("title", ""), "artist": meta.get("artist", ""),
        "bpm": meta.get("bpm"), "key": meta.get("key", ""), "source_id": meta.get("source_id", ""),
        "analyzed": a.get("analyzed"), "basis": a.get("method", {}).get("basis", ""),
        "stems": bool(a.get("method", {}).get("stems")),
        "sections": [s["name"] for s in a.get("structure", {}).get("sections", [])],
        "crest_drop_db": dyn.get("crest_factor_drop_db"), "loudness_strategy": dyn.get("loudness_strategy", ""),
        "bass_type": b.get("type", ""), "bass_profile": b.get("energy", {}).get("profile", ""),
        "sub_rel_db": b.get("energy", {}).get("sub_rel_db"), "fundament_rel_db": b.get("energy", {}).get("fundament_rel_db"),
        "bass_mod_hz": mod.get("primary_hz"), "bass_mod_grid": mod.get("grid_match", ""),
        "bass_mod_source": mod.get("source", ""), "bass_mod_basis": mod.get("basis", ""),
        "bass_mod_confidence": mod.get("confidence", ""),
        "centroid_hz": b.get("timbre", {}).get("spectral_centroid_hz"),
        "sub_side_db": b.get("stereo", {}).get("sub_side_db"),
        "confidence_overall": a.get("confidence_overall", ""),
    }


def main() -> int:
    # Korpus = reference od profesionálů; vlastní tracky (access own_work) do něj nepatří.
    own = set()
    for line in (ROOT / "knowledge" / "sources.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            s = json.loads(line)
            if s.get("access") == "own_work":
                own.add(s["id"])
    rows = []
    for d in sorted(p for p in (ROOT / "data" / "tracks").iterdir() if p.is_dir()):
        m, an = d / "meta.json", d / "analysis.json"
        if m.exists() and an.exists():
            meta = json.loads(m.read_text(encoding="utf-8"))
            if meta.get("source_id") in own:
                continue
            rows.append(row(meta, json.loads(an.read_text(encoding="utf-8"))))
    out = ROOT / "data" / "corpus" / "tracks.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    print(f"{len(rows)} tracků → {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
