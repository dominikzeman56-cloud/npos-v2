import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import build_variace as V

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="chybí node")
JS = Path(__file__).parent / "npos_variace.js"

# stejné prostředí jako Max v8: Dict, outlet, inlet; noty a kontext přijdou v obou pořadích
HARNESS = r"""
const fs = require("fs");
const store = {};
let counter = 0;
global.Dict = function (name) {
  this.name = name || ("d" + (++counter));
  if (!(this.name in store)) store[this.name] = "{}";
  this.stringify = () => store[this.name];
  this.parse = (s) => { store[this.name] = s; };
};
const outs = [];
global.inlets = 0; global.outlets = 0; global.inlet = 0;
global.outlet = (i, ...a) => outs.push([i, ...a]);
const src = fs.readFileSync(process.argv[2], "utf8");
const api = new Function("module", src + "\n;return {dictionary, type, amount, seed, phrase, dice};")({ exports: {} });
const cases = JSON.parse(process.argv[3]);
const results = [];
for (const c of cases) {
  outs.length = 0;
  api.type(c.type); api.amount(c.amount); api.seed(c.seed); api.phrase(c.phrase ?? 1);
  store.ctx = JSON.stringify(c.context || {});
  store.clip = JSON.stringify({ notes: c.notes });
  if (c.order === "notes_first") { global.inlet = 0; api.dictionary("clip"); global.inlet = 1; api.dictionary("ctx"); }
  else { global.inlet = 1; api.dictionary("ctx"); global.inlet = 0; api.dictionary("clip"); }
  const [_, kind, name] = outs.find(o => o[0] === 0);
  results.push(JSON.parse(store[name]).notes);
}
console.log(JSON.stringify(results));
"""

TYPES = ["Konec", "Oktávy", "Chroma", "Ratchet", "Drop 2"]
F_MINOR = {"scale": {"root_note": 5, "scale_intervals": [0, 2, 3, 5, 7, 8, 10]}}


def riff(bars=8):
    """Neuro-ish dvoutakt (F1, Ab1, C2, Eb1) zopakovaný: dlouhé tóny na době i krátké mezi."""
    two = [(0, 1.5, 41), (1.5, 0.5, 44), (2.5, 1.0, 48), (4, 2.0, 39), (6.5, 0.5, 41), (7, 1.0, 44)]
    out, nid = [], 1
    for k in range(bars // 2):
        for s, d, p in two:
            out.append({"note_id": nid, "pitch": p, "start_time": s + 8 * k, "duration": d, "velocity": 100,
                        "mute": 0, "probability": 1, "velocity_deviation": 0, "release_velocity": 64})
            nid += 1
    return out


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    d = tmp_path_factory.mktemp("var")
    (d / "h.js").write_text(HARNESS, encoding="utf-8")
    return d / "h.js"


def run(harness, cases):
    out = subprocess.run([NODE, str(harness), str(JS), json.dumps(cases)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def case(t, **kw):
    c = {"type": TYPES.index(t), "amount": 50, "seed": 3, "phrase": 1, "context": F_MINOR, "notes": riff()}
    c.update(kw)
    return c


def by_id(notes):
    return {n["note_id"]: n for n in notes if "note_id" in n}


def test_konec_changes_only_last_bar_of_phrases(harness):
    orig = by_id(riff())
    (res,) = run(harness, [case("Konec", amount=60)])
    changed = [n for i, n in by_id(res).items() if n["pitch"] != orig[i]["pitch"]]
    assert changed
    for n in changed:
        assert (n["start_time"] % 16) >= 12  # poslední takt čtyřtaktí


def test_oktavy_keep_rhythm_and_downbeats(harness):
    orig = by_id(riff())
    (res,) = run(harness, [case("Oktávy", amount=100)])
    got = by_id(res)
    assert len(res) == len(orig)
    moved = 0
    for i, n in got.items():
        assert n["start_time"] == orig[i]["start_time"]
        diff = n["pitch"] - orig[i]["pitch"]
        assert diff % 12 == 0
        if n["start_time"] % 4 == 0:
            assert diff == 0
        moved += diff != 0
    assert moved


def test_chroma_inserts_semitone_approach(harness):
    (res,) = run(harness, [case("Chroma", amount=100)])
    new = [n for n in res if "note_id" not in n]
    assert new
    for a in new:
        nxt = [n for n in res if abs(n["start_time"] - (a["start_time"] + 0.25)) < 1e-6 and "note_id" in n]
        assert nxt and abs(min(x["pitch"] for x in nxt) - a["pitch"]) == 1
        assert abs((a["start_time"] + 0.25) - round(a["start_time"] + 0.25)) < 1e-6  # cíl je na době


def test_ratchet_splits_long_notes(harness):
    lo, hi = run(harness, [case("Ratchet", amount=60), case("Ratchet", amount=100)])
    assert len(lo) > len(riff())
    steps = {round(n["duration"], 3) for n in hi if "note_id" not in n}
    assert steps and max(steps) <= 0.125  # vysoko 1/32


def test_drop2_keeps_first_phrase(harness):
    orig = by_id(riff())
    (res,) = run(harness, [case("Drop 2", amount=100)])
    for n in res:
        if n["start_time"] < 16 - 1e-6:
            assert "note_id" in n and n["pitch"] == orig[n["note_id"]]["pitch"] and n["start_time"] == orig[n["note_id"]]["start_time"]
    assert any(n["start_time"] >= 16 and ("note_id" not in n or n["pitch"] != orig[n["note_id"]]["pitch"]) for n in res)


def test_deterministic_order_independent_and_seeded(harness):
    a, b, c = run(harness, [case("Drop 2", seed=5), case("Drop 2", seed=5, order="notes_first"), case("Drop 2", seed=6)])
    assert a == b and a != c


def test_amount_zero_is_identity_for_most_types(harness):
    for t in ("Oktávy", "Chroma", "Ratchet"):
        (res,) = run(harness, [case(t, amount=0)])
        assert sorted((n["start_time"], n["pitch"]) for n in res) == sorted((n["start_time"], n["pitch"]) for n in riff())


def test_amxd_is_transformation_and_menus_match_js():
    data = V.amxd_bytes(V.build_patcher(JS.read_text(encoding="utf-8")), kind=b"natt")
    assert data[:12] == b"ampf\x04\x00\x00\x00natt"
    n = struct.unpack("<I", data[28:32])[0]
    patcher = json.loads(data[32:32 + n][:-1].decode("utf-8"))["patcher"]
    assert patcher["project"]["amxdtype"] == 1851880564
    src = JS.read_text(encoding="utf-8").replace(", ", ",")
    assert json.dumps(V.TYPE_LABELS, ensure_ascii=False).replace(", ", ",") in src
    names = [b["box"]["saved_attribute_attributes"]["valueof"]["parameter_longname"]
             for b in patcher["boxes"] if "saved_attribute_attributes" in b["box"]]
    assert len(names) == len(set(names))
