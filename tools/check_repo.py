#!/usr/bin/env python3
"""Kontrola kontraktu repa NPOS (docs/BLUEPRINT.md kap. 9).

Kontroluje:
  * knowledge/sources.jsonl proti core/source.schema.json (bez externích závislostí)
  * frontmatter každého knowledge/**/*.md (knowledge/README.md)
  * že každé source_ids vede do sources.jsonl
  * že data/tracks/<id> má meta.json a že source_id/track odkazy existují
  * že data/presets/*.json sedí na preset-analysis.schema.json a mají source_id ze sources.jsonl
  * (volitelně) že vault_note ze sources.jsonl existuje, je-li vault dostupný
    (cesta z env NPOS_VAULT, výchozí D:\\ObsidianVault\\Hudební produkce)

Návratový kód 0 = bez chyb. Upozornění (warning) kód neovlivňují.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VAULT = r"D:\ObsidianVault\Hudební produkce"

STATUS = {"canon", "candidate", "conditional", "deprecated"}
CONFIDENCE = {"measured", "estimated", "hypothesis"}
TYPES = {"principle", "method", "candidate", "archetype", "producer", "guide", "index"}
SOURCE_TYPES = {"producer_course", "ableton_project", "preset_pack", "interview",
                "track_analysis", "personal_observation", "other"}
RULE_LABELS = {"consensus", "conditional", "school", "dogma_unverified"}
REQUIRED = ("id", "type", "title", "status", "confidence", "source_type", "source_ids", "updated")
EMPTY_OK = {"personal_observation", "other"}
FUNCTIONS = {"sub", "body", "movement", "noise", "texture", "lead", "pad", "fx", "other"}
LOCAL_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:(?:\\\\|\\|/)[^\s\"']*")


def local_paths(root: Path) -> list[str]:
    """Lokální cesty (např. D:\\...) v commitovaných datech mimo presety: data/tracks/**/*.json a data/local-sources.json.
    Zatím jen upozornění (existující soubory je obsahují); presety hlídá přísněji tools/check_presets.py."""
    files = sorted((root / "data" / "tracks").rglob("*.json")) + [root / "data" / "local-sources.json"]
    out = []
    for f in files:
        if not f.is_file() or "_local" in f.parts:
            continue
        hits = LOCAL_PATH.findall(f.read_text(encoding="utf-8"))
        if hits:
            out.append(f"{f.relative_to(root).as_posix()}: lokální cesta v commitovaném souboru ({len(hits)}×, např. {hits[0][:40]!r})")
    return out


INDEX_KEYS = ("id", "source_id", "name", "file", "function", "archetype", "confidence", "cues_basis", "cues")


def load_jsonl(path: Path):
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            rows.append((n, json.loads(line)))
    return rows


def check_schema_value(value, schema, where, errors):
    """Minimální validátor pro podmnožinu JSON Schema, kterou používá source.schema.json."""
    t = schema.get("type")
    if t:
        types = t if isinstance(t, list) else [t]
        py = {"string": str, "integer": int, "number": (int, float), "object": dict,
              "array": list, "null": type(None), "boolean": bool}
        if not any(isinstance(value, py[x]) and not (x == "integer" and isinstance(value, bool)) for x in types):
            errors.append(f"{where}: očekáván typ {types}, je {type(value).__name__}")
            return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: hodnota {value!r} není v {schema['enum']}")
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        errors.append(f"{where}: {value!r} nesedí na vzor {schema['pattern']}")
    if schema.get("format") == "date" and isinstance(value, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        errors.append(f"{where}: {value!r} není datum YYYY-MM-DD")


def check_object(obj, schema, where, errors):
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        if req not in obj:
            errors.append(f"{where}: chybí povinné pole {req!r}")
    if schema.get("additionalProperties") is False:
        for k in obj:
            if k not in props:
                errors.append(f"{where}: nepovolené pole {k!r}")
    for k, v in obj.items():
        if k in props:
            check_schema_value(v, props[k], f"{where}.{k}", errors)


def parse_frontmatter(text: str):
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    meta = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            meta[k] = [x.strip() for x in inner.split(",") if x.strip()] if inner else []
        else:
            if len(v) >= 2 and v[0] == v[-1] == '"':
                v = json.loads(v)
            meta[k] = v
    return meta


def _vault_headings(vault: Path, note: str) -> set[str] | None:
    """Texty nadpisů poznámky (bez backticků, malými písmeny), nebo None, když poznámka není dostupná."""
    p = vault / (note if note.endswith(".md") else note + ".md")
    if not p.is_file():
        return None
    out = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if m:
            out.add(re.sub(r"\s+", " ", m.group(1).replace("`", "")).strip().lower())
    return out


def check_next_step(path: Path, vault: Path) -> list[str]:
    """Struktura a odkazy v next-step.json; kotvy se ověřují proti nadpisům ve vaultu (aplikace je porovnává přesným textem)."""
    errs: list[str] = []
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"{path.name}: neplatný JSON ({e})"]
    phases = {p.get("id") for p in d.get("phases", [])}
    items = d.get("items", [])
    ids = [i.get("id") for i in items]
    for dup in {x for x in ids if ids.count(x) > 1}:
        errs.append(f"{path.name}: duplicitní id {dup!r}")
    for it in items:
        w = f"{path.name}:{it.get('id')}"
        for k in ("id", "phase", "situation", "steps", "sources", "confidence", "vault"):
            if not it.get(k):
                errs.append(f"{w}: chybí {k}")
        if it.get("phase") not in phases:
            errs.append(f"{w}: neznámá fáze {it.get('phase')!r}")
        if it.get("confidence") not in CONFIDENCE:
            errs.append(f"{w}: confidence {it.get('confidence')!r} mimo slovník")
        for t in it.get("then", []):
            if t not in ids:
                errs.append(f"{w}: then → {t!r} neexistuje")
        if vault.is_dir() and it.get("vault"):
            heads = _vault_headings(vault, it["vault"])
            if heads is None:
                errs.append(f"{w}: poznámka {it['vault']!r} ve vaultu nenalezena")
            elif it.get("anchor") and re.sub(r"\s+", " ", it["anchor"].replace("`", "")).strip().lower() not in heads:
                errs.append(f"{w}: kotva {it['anchor']!r} není nadpisem v {it['vault']!r}")
    for p in phases:
        if not any(i.get("phase") == p for i in items):
            errs.append(f"{path.name}: fáze {p!r} nemá žádnou položku")
    return errs


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    errors: list[str] = []
    warnings: list[str] = []

    # --- sources.jsonl
    schema = json.loads((ROOT / "core" / "source.schema.json").read_text(encoding="utf-8"))
    src_path = ROOT / "knowledge" / "sources.jsonl"
    source_ids: set[str] = set()
    sources = []
    if not src_path.exists():
        errors.append("knowledge/sources.jsonl neexistuje")
    else:
        try:
            sources = load_jsonl(src_path)
        except json.JSONDecodeError as e:
            errors.append(f"sources.jsonl: neplatný JSON ({e})")
        for n, row in sources:
            check_object(row, schema, f"sources.jsonl:{n}", errors)
            sid = row.get("id")
            if sid in source_ids:
                errors.append(f"sources.jsonl:{n}: duplicitní id {sid!r}")
            source_ids.add(sid)

    # --- vault_note (volitelně)
    vault = Path(os.environ.get("NPOS_VAULT", DEFAULT_VAULT))
    if vault.is_dir():
        for n, row in sources:
            vn = row.get("vault_note")
            if vn and not (vault / vn).exists():
                warnings.append(f"sources.jsonl:{n}: vault_note {vn!r} ve vaultu nenalezen")
    else:
        warnings.append(f"vault {vault} není dostupný; kontrola vault_note přeskočena")

    # --- knowledge/guides/next-step.json (rozhodovací pomůcka „Co dál?“)
    ns = ROOT / "knowledge" / "guides" / "next-step.json"
    if ns.exists():
        errors.extend(check_next_step(ns, vault))

    # --- knowledge/**/*.md
    seen_ids: dict[str, Path] = {}
    md_files = sorted((ROOT / "knowledge").rglob("*.md"))
    for path in md_files:
        rel = path.relative_to(ROOT).as_posix()
        if path.name == "README.md" and path.parent == ROOT / "knowledge":
            continue  # kontrakt samotný
        meta = parse_frontmatter(path.read_text(encoding="utf-8"))
        if meta is None:
            errors.append(f"{rel}: chybí frontmatter")
            continue
        for f in REQUIRED:
            if f not in meta:
                errors.append(f"{rel}: chybí pole {f!r}")
        if meta.get("type") not in TYPES:
            errors.append(f"{rel}: type {meta.get('type')!r} není v {sorted(TYPES)}")
        if meta.get("status") not in STATUS:
            errors.append(f"{rel}: status {meta.get('status')!r} není v {sorted(STATUS)}")
        if meta.get("confidence") not in CONFIDENCE:
            errors.append(f"{rel}: confidence {meta.get('confidence')!r} není v {sorted(CONFIDENCE)}")
        if meta.get("source_type") not in SOURCE_TYPES:
            errors.append(f"{rel}: source_type {meta.get('source_type')!r} není v {sorted(SOURCE_TYPES)}")
        if "rule_label" in meta and meta["rule_label"] not in RULE_LABELS:
            errors.append(f"{rel}: rule_label {meta['rule_label']!r} není v {sorted(RULE_LABELS)}")
        if "updated" in meta and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(meta["updated"])):
            errors.append(f"{rel}: updated není datum YYYY-MM-DD")
        ids = meta.get("source_ids", [])
        if not isinstance(ids, list):
            errors.append(f"{rel}: source_ids musí být seznam")
            ids = []
        for sid in ids:
            if sid not in source_ids:
                errors.append(f"{rel}: source_id {sid!r} není ve sources.jsonl")
        if not ids and meta.get("source_type") not in EMPTY_OK:
            errors.append(f"{rel}: prázdné source_ids je povoleno jen pro {sorted(EMPTY_OK)}")
        if not ids and meta.get("status") == "canon" and meta.get("type") not in ("index",) \
                and meta.get("source_type") not in EMPTY_OK:
            errors.append(f"{rel}: status canon nesmí mít prázdné source_ids")
        mid = meta.get("id")
        if mid in seen_ids:
            errors.append(f"{rel}: duplicitní id {mid!r} (také {seen_ids[mid].name})")
        elif mid:
            seen_ids[mid] = path

    # --- data/tracks
    tracks_dir = ROOT / "data" / "tracks"
    if tracks_dir.is_dir():
        for d in sorted(p for p in tracks_dir.iterdir() if p.is_dir()):
            meta_p = d / "meta.json"
            if not meta_p.exists():
                errors.append(f"data/tracks/{d.name}: chybí meta.json")
                continue
            m = json.loads(meta_p.read_text(encoding="utf-8"))
            sid = m.get("source_id")
            if sid is None:
                warnings.append(f"data/tracks/{d.name}/meta.json: bez source_id")
            elif sid not in source_ids:
                errors.append(f"data/tracks/{d.name}/meta.json: source_id {sid!r} není ve sources.jsonl")
            for js in ("analysis.json", "build-sheet.json"):
                p = d / js
                if p.exists():
                    try:
                        json.loads(p.read_text(encoding="utf-8"))
                    except json.JSONDecodeError as e:
                        errors.append(f"data/tracks/{d.name}/{js}: neplatný JSON ({e})")

    # --- data/presets
    presets_dir = ROOT / "data" / "presets"
    if presets_dir.is_dir():
        pschema = json.loads((ROOT / "core" / "preset-analysis.schema.json").read_text(encoding="utf-8"))
        for p in sorted(presets_dir.glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"data/presets/{p.name}: neplatný JSON ({e})")
                continue
            check_object(d, pschema, f"data/presets/{p.name}", errors)
            if d.get("source_id") not in source_ids:
                errors.append(f"data/presets/{p.name}: source_id {d.get('source_id')!r} není ve sources.jsonl")
        # kompaktní indexy packů (tools/index_presets.py); plné dumpy jsou v _local/ mimo git
        seen: set[str] = set()
        for p in sorted((presets_dir / "index").glob("*.jsonl")):
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                where = f"data/presets/index/{p.name}:{n}"
                try:
                    d = json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(f"{where}: neplatný JSON ({e})")
                    continue
                miss = [k for k in INDEX_KEYS if k not in d]
                if miss:
                    errors.append(f"{where}: chybí {', '.join(miss)}")
                if d.get("source_id") not in source_ids:
                    errors.append(f"{where}: source_id {d.get('source_id')!r} není ve sources.jsonl")
                if d.get("function") not in FUNCTIONS:
                    errors.append(f"{where}: function {d.get('function')!r} mimo slovník")
                if d.get("confidence") not in CONFIDENCE:
                    errors.append(f"{where}: confidence {d.get('confidence')!r} mimo slovník")
                if d.get("id") in seen:
                    errors.append(f"{where}: duplicitní id {d.get('id')!r}")
                seen.add(d.get("id"))

    # --- schémata jsou platný JSON
    for s in sorted((ROOT / "core").glob("*.schema.json")):
        try:
            json.loads(s.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{s.name}: neplatný JSON ({e})")

    # --- lokální cesty v datech (zatím jen upozornění)
    warnings.extend(local_paths(ROOT))

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    print(f"{len(md_files)} md souborů, {len(source_ids)} zdrojů, {len(errors)} chyb, {len(warnings)} upozornění")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
