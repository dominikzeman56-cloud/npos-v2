"""Sestaví Max for Live MIDI Tool (Transformation) `NPOS Variace.amxd` z `npos_variace.js`.

Stejný formát jako NPOS Skeleton, jen typ `natt` (šablona `Resources/Misc/Max MIDI Tools/Max MIDI Transformation.amxd`).
Bez dat z packů: zařízení jde sdílet.

Použití:
  py -3.12 tools/m4l/build_variace.py --out "D:/Ableton/User Library/MIDI Tools/Max Transformations/NPOS Variace.amxd"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_amxd import AMXD_NATT, Patch, add_control, amxd_bytes, param, patcher_dict  # noqa: E402

HERE = Path(__file__).parent
TYPE_LABELS = ["Konec", "Oktávy", "Chroma", "Ratchet", "Drop 2"]  # stejné jako TYPES v JS
PHRASE_LABELS = ["Fráze 2", "Fráze 4", "Fráze 8"]  # stejné pořadí jako PHRASES v JS


def build_patcher(code: str) -> dict:
    p = Patch()
    mt_in = p.obj("live.miditool.in", [10, 10, 90, 20], ins=1, outs=3)
    js = p.box(maxclass="v8.codebox", code=code, filename="none", fontface=0, fontname="<Monospaced>", fontsize=10.0,
               numinlets=2, numoutlets=2, outlettype=["", ""], patching_rect=[10, 330, 500, 120],
               saved_object_attributes={"parameter_enable": 0}, varname="npos_variace")
    mt_out = p.obj("live.miditool.out", [10, 480, 95, 20], ins=1, outs=0)
    p.line(mt_in, 0, js, 0)
    p.line(mt_in, 1, js, 1)
    p.line(js, 0, mt_out, 0)

    menu_out = (3, ["", "", "float"])
    add_control(p, js, mt_in, "live.menu", "type", param("Typ", "Typ", 2, parameter_enum=TYPE_LABELS,
                parameter_mmax=len(TYPE_LABELS) - 1, parameter_initial=[0], parameter_initial_enable=1),
                [120, 60, 70, 15], [4, 4, 70, 15], "type", *menu_out)
    add_control(p, js, mt_in, "live.menu", "phrase", param("Fraze", "Fráze", 2, parameter_enum=PHRASE_LABELS,
                parameter_mmax=len(PHRASE_LABELS) - 1, parameter_initial=[1], parameter_initial_enable=1),
                [220, 60, 70, 15], [78, 4, 70, 15], "phrase", *menu_out)
    add_control(p, js, mt_in, "live.dial", "amount", param("Mnozstvi", "Množství", 0, parameter_unitstyle=5,
                parameter_mmax=100.0, parameter_initial=[50], parameter_initial_enable=1),
                [320, 60, 44, 48], [4, 26, 44, 48], "amount", 2, ["", "float"])
    seed_ui = add_control(p, js, mt_in, "live.numbox", "seed", param("Seed", "Seed", 1, parameter_unitstyle=0,
                          parameter_mmin=1.0, parameter_mmax=999.0, parameter_initial=[1], parameter_initial_enable=1),
                          [400, 60, 44, 15], [60, 50, 44, 15], "seed", 2, ["", "float"])
    p.line(js, 1, seed_ui, 0)  # kostka: JS pošle nový seed do numboxu, ten spustí nový výpočet

    dice = p.box(maxclass="live.text", mode=0, text="Kostka", numinlets=1, numoutlets=2, outlettype=["", ""],
                 parameter_enable=1, patching_rect=[480, 60, 44, 15], presentation=1, presentation_rect=[106, 50, 42, 15],
                 saved_attribute_attributes=param("Kostka", "Kostka", 2, parameter_enum=["val1", "val2"], parameter_mmax=1.0),
                 varname="dice")
    dice_t = p.obj("t b", [480, 90, 30, 20], ins=1, outs=1, outtype=["bang"])
    dice_m = p.box(maxclass="message", text="dice", numinlets=2, numoutlets=1, outlettype=[""], patching_rect=[480, 120, 40, 20])
    p.line(dice, 0, dice_t, 0)
    p.line(dice_t, 0, dice_m, 0)
    p.line(dice_m, 0, js, 0)

    for text, rect in (("Seed", [60, 34, 44, 14]), ("NPOS Variace", [4, 120, 144, 14])):
        p.box(maxclass="live.comment", text=text, textjustification=0, numinlets=1, numoutlets=0,
              patching_rect=[rect[0] + 700, rect[1], rect[2], rect[3]], presentation=1, presentation_rect=rect)
    return patcher_dict(p, "Switch-upy vlastního riffu: jiný konec, oktávy, chromatické náběhy, ratchet, drop 2 (NPOS).",
                        AMXD_NATT)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    code = (HERE / "npos_variace.js").read_text(encoding="utf-8")
    data = amxd_bytes(build_patcher(code), kind=b"natt")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(data)
    print(f"{a.out}  ({len(data) / 1024:.1f} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
