"""Společné pomocné funkce pro rozbory `.als` a MIDI (als_stats, midi_stats, midi_project, midi_batch, stem_grid).

Jen přesunutý kód bez změny chování: kvartily, podpis mezer v taktu, noty jednoho MIDI klipu.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET


def quant(xs: list[float], digits: int = 3, extremes: bool = False) -> dict:
    """Počet, kvartily (lineární interpolace) a volitelně min a max."""
    s = sorted(xs)
    n = len(s)

    def q(p: float) -> float:
        i = (n - 1) * p
        lo, hi = int(math.floor(i)), int(math.ceil(i))
        return round(s[lo] + (s[hi] - s[lo]) * (i - lo), digits)

    if extremes:
        return {"n": n, "min": s[0], "q1": q(0.25), "median": q(0.5), "q3": q(0.75), "max": s[-1]}
    return {"n": n, "q1": q(0.25), "median": q(0.5), "q3": q(0.75)}


def gap_signature(cells: str, hit: str = "x+") -> str:
    """Vzdálenosti mezi nástupy v jednom taktu (v šestnáctinách), s návratem na začátek taktu: 'x...x..x' -> '4-3-1'."""
    hits = [i for i, c in enumerate(cells) if c in hit]
    if not hits:
        return ""
    if len(hits) == 1:
        return "16"
    gaps = [b - a for a, b in zip(hits, hits[1:])] + [16 - hits[-1] + hits[0]]
    return "-".join(str(g) for g in gaps)


def clip_notes(clip: ET.Element, a: float, b: float, val) -> list[tuple[float, float, int, int]]:
    """Zapnuté noty klipu v okně smyčky [a, b): (začátek od a, délka, výška, velocity), seřazené.
    `val` = als_stats.val (předává se, aby modul nezávisel na als_stats)."""
    notes = []
    for kt in clip.findall("Notes/KeyTracks/KeyTrack"):
        key = val(kt, "MidiKey")
        if key is None:
            continue
        for ev in kt.findall("Notes/MidiNoteEvent"):
            if ev.get("IsEnabled") == "false":
                continue
            s = float(ev.get("Time", "0"))
            if a <= s < b:
                notes.append((s - a, float(ev.get("Duration", "0")), int(key), int(float(ev.get("Velocity", "100")))))
    return sorted(notes)
