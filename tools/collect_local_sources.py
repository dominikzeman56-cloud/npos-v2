#!/usr/bin/env python3
"""collect_local_sources.py — sebere „veškerá data, ze kterých NPOS vychází“ na jedno místo na disku.

Dělá dvě věci:
  1. zapíše manifest `data/local-sources.json` (do gitu): kde každá skupina surových zdrojů fyzicky leží,
     jestli tam ještě je, kolik zabírá a jestli je zkopírovaná;
  2. zkopíruje MALÉ zdroje do `_sources/` (gitignored): přepisy videí, manuály (PDF), použité `.SerumPreset`
     a `.als` projekty. Videa a velké balíky zůstávají na původním místě, v manifestu je jejich cesta.

Soubory z placených kurzů a packů se do gitu nedostanou (`redistribution: none` v `knowledge/sources.jsonl`);
`_sources/` je jen lokální kopie pro tento počítač.

Použití:  py -3.12 tools/collect_local_sources.py [--dry-run] [--no-copy]
Cesty ke zdrojům jsou v `ROOTS` níže, uprav je, pokud se disk změní.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VAULT = Path(r"D:\ObsidianVault\Hudební produkce")
OUT = REPO / "_sources"
MANIFEST = REPO / "data" / "local-sources.json"
LEARNING = Path(r"D:\Ableton\10_Projects\04_Learning")
PROJECTS = Path(r"D:\Ableton\10_Projects")
PRESET_ROOTS = [Path(r"D:\VST\Xfer"), Path(r"D:\Ableton\20_Samples\01_New"), PROJECTS]

sys.path.insert(0, str(REPO / "tools"))


def size_of(files) -> int:
    total = 0
    for f in files:
        try:
            total += os.path.getsize(f)
        except OSError:
            pass
    return total


def walk(root: Path, exts: tuple[str, ...], skip: tuple[str, ...] = ()) -> list[Path]:
    out = []
    if not root.exists():
        return out
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not any(s.lower() in d.lower() for s in skip)]
        out += [Path(dirpath) / f for f in files if f.lower().endswith(exts)]
    return out


def copy(src: Path, dst: Path, dry: bool) -> bool:
    if dry:
        return True
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.stat().st_size == src.stat().st_size:
            return True
        shutil.copy2(src, dst)
        return True
    except OSError as e:
        print("  nelze zkopírovat:", src.name, e, file=sys.stderr)
        return False


def collect_presets(dry: bool) -> dict:
    import analyze_preset as ap  # noqa: E402

    groups = {}  # preset id -> group (project folder) from the committed index, so the layout reproduces the same ids
    for jf in glob.glob(str(REPO / "data" / "presets" / "index" / "*.jsonl")):
        for line in Path(jf).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                groups[r["id"]] = r.get("group") or ""
    wanted: dict[str, tuple[str, str]] = {}  # hash -> (source_id, filename)
    ids: dict[str, str] = {}  # hash -> preset id
    for f in glob.glob(str(REPO / "data" / "presets" / "_local" / "*" / "*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        h = (d.get("reading") or {}).get("preset_hash")
        if h:
            wanted[h] = (d.get("source_id", "unknown"), (d.get("reading") or {}).get("file") or "")
            ids[h] = d.get("id", "")
    names = {fn for _, fn in wanted.values()}
    found = {}
    for root in PRESET_ROOTS:
        for p in walk(root, (".serumpreset",)):
            if p.name not in names:
                continue
            try:
                meta, _, _ = ap.decode_preset(p.read_bytes())
            except Exception:
                continue
            h = meta.get("hash")
            if h in wanted and h not in found:
                found[h] = p
    copied = 0
    for h, p in found.items():
        sid, _ = wanted[h]
        group = groups.get(ids.get(h, ""), "") or p.parent.name
        if copy(p, OUT / "presets" / sid / group / p.name, dry):  # group = project folder, as in the committed index
            copied += 1
    return {"wanted": len(wanted), "found": len(found), "copied": copied, "size": size_of(found.values())}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--dry-run", action="store_true", help="nic nekopíruj, jen vypiš a zapiš manifest")
    ap_.add_argument("--no-copy", action="store_true", help="jen manifest")
    a = ap_.parse_args()
    dry = a.dry_run or a.no_copy

    sections = []

    def add(sid, label, path, files, copied_to, note, copy_list=None):
        entry = {"id": sid, "label": label, "path": str(path), "exists": Path(path).exists(), "files": len(files),
                 "size_mb": round(size_of(files) / 1048576, 1), "copied_to": copied_to, "note": note}
        sections.append(entry)
        if copy_list is not None and not dry:
            ok = sum(1 for src, dst in copy_list if copy(src, dst, dry))
            entry["copied_files"] = ok
        return entry

    # 1) přepisy + videa
    wv = VAULT / "workshop videos"
    videos = walk(wv, (".mp4", ".mkv", ".webm"), skip=("transcripts",))
    trans = [p for p in walk(wv / "transcripts", (".txt", ".srt", ".json"))] + [p for p in wv.glob("*") if p.suffix.lower() in (".txt", ".srt", ".json")]
    trans = list({str(p): p for p in trans}.values())
    add("workshop-videos", "Videa workshopů a kurzů", wv, videos, None,
        "Placené/stažené videa. Zůstávají na místě (velká), v manifestu jen cesta a velikost.")
    sections[-1]["items"] = [{"file": p.name, "size_mb": round(p.stat().st_size / 1048576, 1)} for p in sorted(videos)]
    add("transcripts", "Přepisy videí (txt/srt/json)", wv / "transcripts", trans, "_sources/transcripts",
        "Přepisy (faster-whisper). Základ pro rozbory s časovými značkami.",
        [(p, OUT / "transcripts" / p.name) for p in trans])

    # 2) manuály
    manuals = [VAULT / "Serum 2 User Guide.pdf", VAULT / "live12-manual-en.pdf"]
    manuals = [m for m in manuals if m.exists()]
    add("manuals", "Manuály (Serum 2, Live 12)", VAULT, manuals, "_sources/manuals", "PDF, ze kterých se čerpá terminologie a popis parametrů.",
        [(m, OUT / "manuals" / m.name) for m in manuals])

    # 3) projekty .als
    learn = walk(LEARNING, (".als",), skip=("backup",))
    add("projects-learning", "Projekty z kurzů (.als, bez Backup)", LEARNING, learn, "_sources/projects/04_Learning",
        "Letsynthesize, Joe Ford a další. Jen .als, samply se nekopírují.",
        [(p, OUT / "projects" / "04_Learning" / p.relative_to(LEARNING)) for p in learn])
    own = walk(PROJECTS / "00_Active", (".als",), skip=("backup",)) + walk(PROJECTS / "01_Template", (".als",), skip=("backup",))
    add("projects-own", "Vlastní projekty a šablona (.als)", PROJECTS, own, "_sources/projects/own",
        "Vlastní tvorba není důkaz v kánonu (pravidlo pravdivosti), jen archiv.",
        [(p, OUT / "projects" / "own" / p.relative_to(PROJECTS)) for p in own])

    # 4) presety použité v indexech
    pr = collect_presets(dry)
    sections.append({"id": "serum-presets-used", "label": "Serum 2 presety použité v indexech", "path": ", ".join(str(r) for r in PRESET_ROOTS),
                     "exists": True, "files": pr["found"], "size_mb": round(pr["size"] / 1048576, 1), "copied_to": "_sources/presets",
                     "note": f"Nalezeno {pr['found']} z {pr['wanted']} (shoda podle hash). Plné balíky (4,8 GB) zůstávají na místě.",
                     "copied_files": pr["copied"]})

    # 5) vault a repo
    sections.append({"id": "vault", "label": "Vault Hudební produkce (kánon)", "path": str(VAULT), "exists": VAULT.exists(), "files": None,
                     "size_mb": None, "copied_to": "mimo git, záloha v D:\\_Backups", "note": "Kánon 10–80, rozbory 60, archiv 90. Není v gitu."})

    manifest = {"generated": date.today().isoformat(), "note": "Kde fyzicky leží zdroje, ze kterých NPOS vychází. Generuje tools/collect_local_sources.py. "
                "Placený obsah se do gitu nedostane, `_sources/` je gitignored.", "sections": sections}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in sections:
        print(f"{s['id']:<22} {s['files'] if s['files'] is not None else '-':>6} souborů  {s['size_mb'] if s['size_mb'] is not None else '-':>8} MB  {'OK' if s['exists'] else 'CHYBÍ'}  {s['path'][:60]}")
    print("manifest:", MANIFEST, "(dry-run)" if dry else "")


if __name__ == "__main__":
    main()
