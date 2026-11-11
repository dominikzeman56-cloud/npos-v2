"""Náhled generátoru bez Live: vypíše mřížku 1/16 po taktech a výšky. Jen pro ladění.

Použití: py -3.12 tools/m4l/preview.py --role bass --seed 3 --bars 4 [--density 50 --variation 30 --key F]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_amxd as B
from test_m4l_skeleton import HARNESS, ROLES

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MINOR = [0, 2, 3, 5, 7, 8, 10]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="bass", choices=ROLES)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--bars", type=int, default=4)
    ap.add_argument("--density", type=int, default=50)
    ap.add_argument("--variation", type=int, default=30)
    ap.add_argument("--key", default="F")
    ap.add_argument("--model", type=Path, default=Path("data/midi/_local/midi-model.json"))
    a = ap.parse_args()
    bar_idx = [0, 1, 2, 4, 8, 16].index(a.bars)
    ctx = {"scale": {"root_note": NAMES.index(a.key), "scale_intervals": MINOR}}
    case = {"role": ROLES.index(a.role), "bars": bar_idx, "density": a.density, "variation": a.variation,
            "seed": a.seed, "octave": 0, "context": ctx}
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "dev.js").write_text(B.js_source(json.loads(a.model.read_text(encoding="utf-8"))), encoding="utf-8")
        (Path(d) / "h.js").write_text(HARNESS, encoding="utf-8")
        out = subprocess.run(["node", str(Path(d) / "h.js"), str(Path(d) / "dev.js"), json.dumps([case])],
                             capture_output=True, text=True, check=True)
    notes = json.loads(out.stdout)[0]["notes"]
    for b in range(a.bars):
        cells = ["."] * 16
        names = []
        for n in sorted(notes, key=lambda n: (n["start_time"], n["pitch"])):
            if b * 4 <= n["start_time"] < b * 4 + 4:
                cells[int(round((n["start_time"] - b * 4) * 4)) % 16] = "x"
                names.append(f"{NAMES[n['pitch'] % 12]}{n['pitch'] // 12 - 2}")
        grid = " ".join("".join(cells[i:i + 4]) for i in range(0, 16, 4))
        print(f"takt {b + 1}: {grid}   {' '.join(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
