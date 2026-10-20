"""Čtečka struktury Ableton Live setů (.als) a souhrnné statistiky. Jen čtení, jen čísla.

Cíl: změřit, jak vypadají reálné projekty (kolik tracků, skupin, returnů, jaké pluginy, jak
často Utility se sníženým gainem nebo high-pass na kicku), než se navrhne nová šablona.
Plné cesty ani názvy projektů a tracků se do výstupu nedostanou: projekt je jen krátký hash.

Pravidla projektu:
- `.als` se jen čte (gzip + XML), nikdy nezapisuje.
- Vlastní tvorba uživatele (složka `own`) není důkaz v kánonu: počítá se zvlášť a do referenčních
  statistik nevstupuje.
- Skupina s méně než 10 projekty dostane jen počet.
- Štítky jistoty: čísla ze souboru jsou `naměřeno`; výklad (co je "past") je `hypotéza`.

Použití:
  py -3.12 tools/als_stats.py --roots _sources/projects --out data/als/als-stats.json
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

try:
    import midi_common as C
except ImportError:  # spuštěno z kořene repa
    sys.path.insert(0, str(Path(__file__).parent))
    import midi_common as C

MIN_N = 10
KICK_RE = re.compile(r"(?<![a-z])(kick|kck|bd)(?![a-z])", re.I)
# Eq8 Mode: 0 = low cut 48 dB, 1 = low cut 12 dB
LOW_CUT_MODES = {"0", "1"}
TRIM_DB = -1.0  # Utility s gainem pod touto hodnotou se počítá jako "ubrané"
HP_KICK_HZ = 60.0


def read_set(path: Path) -> ET.Element:
    with gzip.open(path, "rb") as f:
        return ET.fromstring(f.read())


def val(e: ET.Element | None, path: str, attr: str = "Value") -> str | None:
    if e is None:
        return None
    x = e.find(path)
    return None if x is None else x.get(attr)


def track_name(t: ET.Element) -> str:
    return val(t, "Name/EffectiveName") or ""


def plugin_name(d: ET.Element) -> str | None:
    pd = d.find("PluginDesc")
    if pd is None:
        return None
    for tag, sub in (("VstPluginInfo", "PlugName"), ("Vst3PluginInfo", "Name"), ("AuPluginInfo", "Name")):
        v = val(pd, f"{tag}/{sub}")
        if v:
            return v
    return None


def devices(t: ET.Element) -> list[ET.Element]:
    d = t.find("DeviceChain/DeviceChain/Devices")
    return list(d) if d is not None else []


def lin_to_db(x: float) -> float:
    return -math.inf if x <= 0 else 20.0 * math.log10(x)


def analyze(root: ET.Element) -> dict:
    ls = root.find("LiveSet")
    if ls is None:
        raise ValueError("chybí LiveSet")
    tn = ls.find("Tracks")
    tracks = list(tn) if tn is not None else []
    types = Counter(t.tag for t in tracks)
    main = ls.find("MainTrack")
    plugins: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    trims = 0
    kick_hp = 0
    kick_tracks = 0
    empty_midi = 0
    clips = 0
    depth_max = 0
    ids = {t.get("Id"): t for t in tracks if t.tag == "GroupTrack"}

    def depth(t: ET.Element) -> int:
        d, seen = 0, set()
        g = val(t, "TrackGroupId")
        while g not in (None, "-1") and g in ids and g not in seen:
            seen.add(g)
            d += 1
            g = val(ids[g], "TrackGroupId")
        return d

    for t in tracks:
        depth_max = max(depth_max, depth(t))
        devs = devices(t)
        if t.tag == "MidiTrack" and not devs:
            empty_midi += 1
        is_kick = bool(KICK_RE.search(track_name(t))) and t.tag in ("MidiTrack", "AudioTrack")
        kick_tracks += is_kick
        hp_here = False
        for d in devs:
            kinds[d.tag] += 1
            pn = plugin_name(d)
            if pn:
                plugins[pn] += 1
            if d.tag == "StereoGain" and t.tag != "ReturnTrack":
                g = val(d, "Gain/Manual")
                if g is not None and lin_to_db(float(g)) < TRIM_DB:
                    trims += 1
            if d.tag == "Eq8" and is_kick:
                for b in d:
                    if not b.tag.startswith("Bands."):
                        continue
                    a = b.find("ParameterA")
                    if a is not None and val(a, "IsOn/Manual") == "true" and val(a, "Mode/Manual") in LOW_CUT_MODES:
                        f = val(a, "Freq/Manual")
                        if f is not None and float(f) >= HP_KICK_HZ:
                            hp_here = True
        kick_hp += hp_here
        clips += len(t.findall(".//ArrangerAutomation/Events/MidiClip")) + len(t.findall(".//AudioClip"))
    md = main.find("DeviceChain/DeviceChain/Devices") if main is not None else None
    main_devs = [d.tag for d in md] if md is not None else []
    tempo = val(main, "DeviceChain/Mixer/Tempo/Manual")
    locs = ls.findall("Locators/Locators/Locator")
    return {
        "tracks": len(tracks) - types["ReturnTrack"],
        "midi": types["MidiTrack"],
        "audio": types["AudioTrack"],
        "groups": types["GroupTrack"],
        "returns": types["ReturnTrack"],
        "group_depth": depth_max,
        "empty_midi_tracks": empty_midi,
        "locators": len(locs),
        "tempo": float(tempo) if tempo else None,
        "main_devices": len(main_devs),
        "main_chain": main_devs,
        "utility_trims": trims,
        "kick_tracks": kick_tracks,
        "kick_highpass": kick_hp,
        "device_kinds": dict(kinds),
        "plugins": dict(plugins),
    }


def quant(xs: list[float]) -> dict:
    return C.quant(xs, digits=2, extremes=True)


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    if n < MIN_N:
        return {"n_projects": n, "note": "méně než 10 projektů: jen počet"}
    out: dict = {"n_projects": n}
    for k in ("tracks", "groups", "returns", "group_depth", "locators", "utility_trims", "main_devices", "empty_midi_tracks"):
        out[k] = quant([r[k] for r in rows])
    out["share_with_kick_track"] = round(sum(r["kick_tracks"] > 0 for r in rows) / n, 2)
    kt = [r for r in rows if r["kick_tracks"] > 0]
    out["kick_highpass_ge60hz"] = {"projects": sum(r["kick_highpass"] > 0 for r in kt), "of": len(kt)}
    out["share_with_utility_trim"] = round(sum(r["utility_trims"] > 0 for r in rows) / n, 2)
    out["tempo"] = dict(Counter(round(r["tempo"]) for r in rows if r["tempo"]).most_common(6))
    pl: Counter[str] = Counter()
    mc: Counter[str] = Counter()
    for r in rows:
        pl.update(set(r["plugins"]))
        mc.update(set(r["main_chain"]))
    out["plugins_by_projects"] = dict(pl.most_common(40))
    out["main_chain_by_projects"] = dict(mc.most_common(12))
    return out


def find_sets(roots: list[Path]) -> list[tuple[str, Path, Path]]:
    found = []
    for root in roots:
        for p in sorted(root.rglob("*.als")):
            if "Backup" in p.parts:
                continue
            rel = p.relative_to(root)
            group = "own" if rel.parts and rel.parts[0].lower() == "own" else "reference"
            found.append((group, root, p))
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roots", nargs="+", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path("data/als/als-stats.json"))
    a = ap.parse_args(argv)
    for r in a.roots:
        if not r.is_dir():
            print(f"složka neexistuje: {r}", file=sys.stderr)
            return 2
    rows: list[dict] = []
    failed: Counter[str] = Counter()
    for group, root, p in find_sets(a.roots):
        try:
            row = analyze(read_set(p))
        except (OSError, EOFError, ET.ParseError, ValueError) as e:
            failed[type(e).__name__] += 1
            continue
        row["group"] = group
        row["id"] = hashlib.sha1(f"{group}/{p.relative_to(root)}".encode()).hexdigest()[:8]
        rows.append(row)
    ref = [r for r in rows if r["group"] == "reference"]
    own = [r for r in rows if r["group"] == "own"]
    result = {
        "basis": "als_file",
        "confidence": "naměřeno",
        "note": "Čísla ze struktury setů. Reference = kurzy a cizí projekty. Vlastní tvorba je zvlášť a není důkaz. Výklad 'past' je hypotéza.",
        "failed": dict(failed),
        "reference": summarize(ref),
        "own": summarize(own),
        "projects": [{k: v for k, v in r.items() if k in ("id", "group", "tracks", "groups", "returns", "locators", "utility_trims", "kick_tracks", "kick_highpass", "main_devices", "tempo")} for r in rows],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"projects: {len(rows)} (reference {len(ref)}, own {len(own)}), unreadable: {sum(failed.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
