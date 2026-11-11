"""Sestaví Max for Live MIDI Tool (Generator) `NPOS Skeleton.amxd` z `npos_skeleton.js` a modelu z `midi_model.py`.

Formát .amxd podle Abletonovy šablony `Resources/Misc/Max MIDI Tools/Max MIDI Generator.amxd`:
  b"ampf" <u32 LE 4> b"nagg" (Note Generator) | b"meta" <u32 4> 4× 0 | b"ptch" <u32 délka> JSON patcheru + "\\n\\0"
JS je vložený do patcheru přes `v8.codebox` (Max 9), takže zařízení je jeden soubor bez závislostí.

POZOR: model obsahuje rytmy i z placených packů, hotové zařízení je pro osobní použití.

Použití:
  py -3.12 tools/m4l/build_amxd.py --model data/midi/_local/midi-model.json \\
      --out "D:/Ableton/User Library/MIDI Tools/Max Generators/NPOS Skeleton.amxd"
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).parent
AMXD_NAGG = 1851877223  # "nagg" jako u32 big-endian, stejné číslo jako v šabloně
AMXD_NATT = 1851880564  # "natt" = Note Transformation
KEEP = ("enough", "slot_prob", "rhythms", "rhythms2", "density", "dur16", "vel", "offsets", "octave_up", "motion")
ROLE_LABELS = ["Sub", "Bass", "Reese", "Stab", "Lead", "Pad", "Kick", "Snare", "Hats", "Drums"]  # stejné pořadí jako ROLES v JS
VOICE_LABELS = ["Auto", "Mono", "Kvinta", "Oktáva", "Akord", "Akord 9"]  # stejné jako VOICINGS v JS
LINK_LABELS = ["Volně", "Harm", "Odpověď"]  # stejné jako LINKS v JS
BAR_LABELS = ["Výběr", "1 takt", "2 takty", "4 takty", "8 taktů", "16 taktů"]


def compact_model(model: dict) -> dict:
    out = {"roles": {r: {k: v[k] for k in KEEP if k in v} for r, v in model["roles"].items()}}
    for k in ("phrases", "forms", "progressions"):  # fráze a progrese z packů s tóninou v názvu
        if k in model:
            out[k] = model[k]
    return out


def js_source(model: dict) -> str:
    src = (HERE / "npos_skeleton.js").read_text(encoding="utf-8")
    marker = "/*MODEL*/ null"
    if marker not in src:
        raise ValueError("v npos_skeleton.js chybí značka /*MODEL*/ null")
    return src.replace(marker, json.dumps(compact_model(model), separators=(",", ":")))


class Patch:
    def __init__(self) -> None:
        self.boxes: list[dict] = []
        self.lines: list[dict] = []
        self.n = 0

    def box(self, **kw) -> str:
        self.n += 1
        bid = f"obj-{self.n}"
        self.boxes.append({"box": {"id": bid, **kw}})
        return bid

    def obj(self, text: str, rect: list[float], ins: int = 1, outs: int = 1, outtype: list[str] | None = None) -> str:
        return self.box(maxclass="newobj", text=text, numinlets=ins, numoutlets=outs,
                        outlettype=outtype if outtype is not None else [""] * outs, patching_rect=rect)

    def line(self, src: str, out: int, dst: str, inl: int) -> None:
        self.lines.append({"patchline": {"source": [src, out], "destination": [dst, inl]}})


def param(longname: str, shortname: str, ptype: int, **extra) -> dict:
    v = {"parameter_longname": longname, "parameter_shortname": shortname, "parameter_type": ptype}
    v.update(extra)
    return {"valueof": v}


def add_control(p: Patch, js: str, mt_in: str, maxclass: str, name: str, valueof: dict, rect_p: list[float],
                rect_ui: list[float], msg: str, outs: int, outtype: list[str], **kw) -> str:
    """Ovladač v presentation: hodnota jako zpráva `msg` do JS, pak bang do live.miditool.in (nový výpočet)."""
    ui = p.box(maxclass=maxclass, numinlets=1, numoutlets=outs, outlettype=outtype, parameter_enable=1,
               patching_rect=rect_p, presentation=1, presentation_rect=rect_ui,
               saved_attribute_attributes=valueof, varname=name, **kw)
    x, y = rect_p[0], rect_p[1] + rect_p[3] + 8
    trig = p.obj("t b l", [x, y, 40, 20], ins=1, outs=2)
    pre = p.obj(f"prepend {msg}", [x + 46, y + 26, 80, 20], ins=1, outs=1)
    p.line(ui, 0, trig, 0)
    p.line(trig, 1, pre, 0)   # hodnota do JS (pravý výstup triggeru jde první)
    p.line(pre, 0, js, 0)
    p.line(trig, 0, mt_in, 0)  # pak bang: Live vydá klip a JS spočítá znovu
    return ui


def build_patcher(code: str) -> dict:
    p = Patch()
    mt_in = p.obj("live.miditool.in", [10, 10, 90, 20], ins=1, outs=3)
    js = p.box(maxclass="v8.codebox", code=code, filename="none", fontface=0, fontname="<Monospaced>", fontsize=10.0,
               numinlets=2, numoutlets=2, outlettype=["", ""], patching_rect=[10, 330, 500, 120],
               saved_object_attributes={"parameter_enable": 0}, varname="npos_skeleton")
    mt_out = p.obj("live.miditool.out", [10, 480, 95, 20], ins=1, outs=0)
    p.line(mt_in, 0, js, 0)
    p.line(mt_in, 1, js, 1)
    p.line(js, 0, mt_out, 0)

    def control(*a, **kw) -> str:
        return add_control(p, js, mt_in, *a, **kw)

    menu_out = (3, ["", "", "float"])
    control("live.menu", "role", param("Role", "Role", 2, parameter_enum=ROLE_LABELS, parameter_mmax=len(ROLE_LABELS) - 1,
                                       parameter_initial=[1], parameter_initial_enable=1),
            [120, 60, 70, 15], [4, 4, 70, 15], "role", *menu_out)
    control("live.menu", "bars", param("Takty", "Takty", 2, parameter_enum=BAR_LABELS, parameter_mmax=len(BAR_LABELS) - 1,
                                       parameter_initial=[0], parameter_initial_enable=1),
            [220, 60, 70, 15], [78, 4, 70, 15], "bars", *menu_out)
    dial_out = (2, ["", "float"])
    control("live.dial", "density", param("Hustota", "Hustota", 0, parameter_unitstyle=5, parameter_mmax=100.0,
                                          parameter_initial=[50], parameter_initial_enable=1),
            [320, 60, 44, 48], [4, 24, 44, 48], "density", *dial_out)
    control("live.dial", "variation", param("Variace", "Variace", 0, parameter_unitstyle=5, parameter_mmax=100.0,
                                            parameter_initial=[30], parameter_initial_enable=1),
            [400, 60, 44, 48], [52, 24, 44, 48], "variation", *dial_out)
    control("live.dial", "legato", param("Legato", "Legato", 0, parameter_unitstyle=5, parameter_mmax=100.0,
                                         parameter_initial=[50], parameter_initial_enable=1),
            [880, 60, 44, 48], [100, 24, 44, 48], "legato", *dial_out)
    control("live.numbox", "octave", param("Oktava", "Okt", 1, parameter_unitstyle=0, parameter_mmin=-2.0,
                                           parameter_mmax=2.0, parameter_initial=[0], parameter_initial_enable=1),
            [480, 60, 44, 15], [102, 96, 44, 15], "octave", *dial_out)
    control("live.menu", "voicing", param("Hlas", "Hlas", 2, parameter_enum=VOICE_LABELS, parameter_mmax=len(VOICE_LABELS) - 1,
                                          parameter_initial=[0], parameter_initial_enable=1),
            [960, 60, 70, 15], [30, 120, 62, 15], "voicing", *menu_out)
    control("live.menu", "link", param("Vazba", "Vazba", 2, parameter_enum=LINK_LABELS, parameter_mmax=len(LINK_LABELS) - 1,
                                       parameter_initial=[1], parameter_initial_enable=1),
            [1040, 60, 70, 15], [96, 120, 52, 15], "link", *menu_out)
    seed_ui = control("live.numbox", "seed", param("Seed", "Seed", 1, parameter_unitstyle=0, parameter_mmin=1.0,
                                                  parameter_mmax=999.0, parameter_initial=[1], parameter_initial_enable=1),
                      [560, 60, 44, 15], [4, 96, 44, 15], "seed", *dial_out)
    p.line(js, 1, seed_ui, 0)  # kostka: JS pošle nový seed do numboxu, ten spustí generování

    dice = p.box(maxclass="live.text", mode=0, text="Kostka", numinlets=1, numoutlets=2, outlettype=["", ""],
                 parameter_enable=1, patching_rect=[640, 60, 44, 15], presentation=1, presentation_rect=[52, 96, 44, 15],
                 saved_attribute_attributes=param("Kostka", "Kostka", 2, parameter_enum=["val1", "val2"], parameter_mmax=1.0),
                 varname="dice")
    dice_t = p.obj("t b", [640, 90, 30, 20], ins=1, outs=1, outtype=["bang"])
    dice_m = p.box(maxclass="message", text="dice", numinlets=2, numoutlets=1, outlettype=[""], patching_rect=[640, 120, 40, 20])
    p.line(dice, 0, dice_t, 0)
    p.line(dice_t, 0, dice_m, 0)
    p.line(dice_m, 0, js, 0)

    for text, rect in (("Okt", [102, 80, 44, 14]), ("Seed", [4, 80, 44, 14]), ("Hlas", [4, 120, 26, 14])):
        p.box(maxclass="live.comment", text=text, textjustification=0, numinlets=1, numoutlets=0,
              patching_rect=[rect[0] + 700, rect[1], rect[2], rect[3]], presentation=1, presentation_rect=rect)

    return patcher_dict(p, "Neurofunk/DnB kostry z naměřených referencí (NPOS).", AMXD_NAGG)


def patcher_dict(p: "Patch", description: str, amxdtype: int) -> dict:
    """Obálka patcheru podle Abletonovy šablony MIDI Tools (152×147, presentation)."""
    return {"patcher": {
        "fileversion": 1,
        "appversion": {"major": 9, "minor": 0, "revision": 0, "architecture": "x64", "modernui": 1},
        "classnamespace": "box",
        "rect": [100.0, 100.0, 900.0, 520.0],
        "openrect": [0.0, 0.0, 152.0, 147.0],
        "bglocked": 0,
        "openinpresentation": 1,
        "default_fontsize": 10.0,
        "default_fontface": 0,
        "default_fontname": "Arial Bold",
        "gridonopen": 1,
        "gridsize": [8.0, 8.0],
        "gridsnaponopen": 1,
        "objectsnaponopen": 1,
        "statusbarvisible": 2,
        "toolbarvisible": 1,
        "boxanimatetime": 500,
        "enablehscroll": 1,
        "enablevscroll": 1,
        "devicewidth": 152.0,
        "description": description,
        "digest": "",
        "tags": "",
        "style": "",
        "subpatcher_template": "",
        "assistshowspatchername": 0,
        "boxes": p.boxes,
        "lines": p.lines,
        "dependency_cache": [],
        "latency": 0,
        "is_mpe": 0,
        "minimum_live_version": "",
        "minimum_max_version": "",
        "platform_compatibility": 0,
        "project": {
            "version": 1, "creationdate": 3590052493, "modificationdate": 3590052493,
            "viewrect": [25.0, 124.0, 300.0, 500.0], "autoorganize": 1, "hideprojectwindow": 1, "showdependencies": 1,
            "autolocalize": 0, "contents": {"patchers": {}}, "layout": {}, "searchpath": {}, "detailsvisible": 0,
            "amxdtype": amxdtype, "readonly": 0, "devpathtype": 0, "devpath": ".", "sortmode": 0, "viewmode": 0,
            "includepackages": 0,
        },
        "autosave": 0,
    }}


def amxd_bytes(patcher: dict, kind: bytes = b"nagg") -> bytes:
    """kind: b"nagg" = Note Generator, b"natt" = Note Transformation (podle šablon v Resources/Misc)."""
    body = (json.dumps(patcher, ensure_ascii=False, indent="\t") + "\n").encode("utf-8") + b"\x00"
    return (b"ampf" + struct.pack("<I", 4) + kind
            + b"meta" + struct.pack("<I", 4) + b"\x00\x00\x00\x00"
            + b"ptch" + struct.pack("<I", len(body)) + body)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, default=Path("data/midi/_local/midi-model.json"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    model = json.loads(a.model.read_text(encoding="utf-8"))
    data = amxd_bytes(build_patcher(js_source(model)))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(data)
    print(f"{a.out}  ({len(data) / 1024:.1f} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
