import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import build_amxd as B

REPO = Path(__file__).resolve().parents[2]
MODEL = REPO / "data/midi/_local/midi-model.json"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(not MODEL.exists() or not NODE, reason="chybí lokální model nebo node")

# Napodobí prostředí Max v8: Dict, outlet, inlet. Pak zavolá stejné funkce, jaké volá patch.
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
const fn = new Function("module", "inlet_ref", src + "\n;return {dictionary, role, bars, density, variation, seed, octave, legato, voicing, link, dice, generate};");
const mod = { exports: {} };
const api = fn(mod);
const cases = JSON.parse(process.argv[3]);
const results = [];
for (const c of cases) {
  outs.length = 0;
  api.role(c.role); api.bars(c.bars); api.density(c.density); api.variation(c.variation);
  api.seed(c.seed); api.octave(c.octave); api.legato(c.legato ?? 50); api.voicing(c.voicing ?? 0); api.link(c.link ?? 1);
  // live.miditool.in: noty (inlet 0) a kontext (inlet 1), pořadí podle c.order
  store.ctx = JSON.stringify(c.context || {});
  store.clip = JSON.stringify({ notes: [] });
  const sendCtx = () => { global.inlet = 1; api.dictionary("ctx"); };
  const sendClip = () => { global.inlet = 0; api.dictionary("clip"); };
  if (c.order === "notes_first") { sendClip(); if (outs.length) throw new Error("generoval před kontextem"); sendCtx(); }
  else { sendCtx(); sendClip(); }
  const [_, kind, name] = outs.find(o => o[0] === 0);
  results.push({ kind, notes: JSON.parse(store[name]).notes });
}
outs.length = 0; api.dice();
results.push({ dice: outs });
console.log(JSON.stringify(results));
"""

ROLES = ["sub", "bass", "reese", "stab", "lead", "harmony", "kick", "snare", "hats", "drums"]
VOICES = ["Auto", "Mono", "Kvinta", "Oktáva", "Akord", "Akord 9"]
F_MINOR = {"scale": {"root_note": 5, "scale_intervals": [0, 2, 3, 5, 7, 8, 10]}}
CS_PHRYG = {"scale": {"root_note": 1, "scale_intervals": [0, 1, 3, 5, 7, 8, 10]},
            "time_selection": {"start_time": 8.0, "end_time": 40.0}}


@pytest.fixture(scope="module")
def js(tmp_path_factory):
    d = tmp_path_factory.mktemp("m4l")
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    (d / "dev.js").write_text(B.js_source(model), encoding="utf-8")
    (d / "harness.js").write_text(HARNESS, encoding="utf-8")
    return d


def run(js, cases, dice=False):
    out = subprocess.run([NODE, str(js / "harness.js"), str(js / "dev.js"), json.dumps(cases)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    return data[-1] if dice else data[:-1]


def case(role, **kw):
    c = {"role": ROLES.index(role), "bars": 3, "density": 50, "variation": 30, "seed": 7, "octave": 0, "context": F_MINOR}
    c.update(kw)
    return c


def test_every_role_generates_valid_notes(js):
    res = run(js, [case(r) for r in ROLES])
    for role, r in zip(ROLES, res):
        assert r["kind"] == "dictionary"
        notes = r["notes"]
        assert notes, role
        for n in notes:
            assert set(n) >= {"pitch", "start_time", "duration", "velocity", "mute", "probability"}
            assert 0 <= n["start_time"] < 16 and n["duration"] > 0, (role, n)
            assert 0 <= n["pitch"] <= 127 and 1 <= n["velocity"] <= 127, (role, n)


def test_pitched_roles_stay_in_clip_scale(js):
    allowed = {(5 + i) % 12 for i in F_MINOR["scale"]["scale_intervals"]}
    res = run(js, [case(r, seed=s) for r in ("sub", "bass", "lead", "harmony") for s in (1, 2, 3)])
    for r in res:
        assert {n["pitch"] % 12 for n in r["notes"]} <= allowed


def test_stab_adds_fifth_and_sub_is_low(js):
    stab, sub = run(js, [case("stab"), case("sub")])
    assert all(n["pitch"] < 48 for n in sub["notes"])  # sub pod C2
    starts = {}
    for n in stab["notes"]:
        starts.setdefault(n["start_time"], []).append(n["pitch"])
    assert any(sorted(v)[-1] - sorted(v)[0] == 7 for v in starts.values())


def test_kick_on_one_and_drums_map(js):
    kick, drums = run(js, [case("kick", seed=s) for s in (1,)] + [case("drums")])
    assert {n["pitch"] for n in kick["notes"]} == {36}
    assert any(n["start_time"] == 0 for n in kick["notes"])
    assert {n["pitch"] for n in drums["notes"]} <= {36, 38, 42}


def test_deterministic_and_seed_changes_output(js):
    a, b, c = run(js, [case("bass", seed=5), case("bass", seed=5), case("bass", seed=6)])
    assert a["notes"] == b["notes"] and a["notes"] != c["notes"]


def test_time_selection_and_scale_from_context(js):
    r = run(js, [case("bass", bars=0, context=CS_PHRYG)])[0]
    assert min(n["start_time"] for n in r["notes"]) >= 8.0
    assert max(n["start_time"] for n in r["notes"]) < 40.0
    allowed = {(1 + i) % 12 for i in CS_PHRYG["scale"]["scale_intervals"]}
    assert {n["pitch"] % 12 for n in r["notes"]} <= allowed


def test_context_after_notes_still_used(js):
    # ve videu z Live jel generátor se starým kontextem: musí počkat na noty i kontext v libovolném pořadí
    a, b = run(js, [case("bass", bars=0, context=CS_PHRYG, order="notes_first"), case("bass", bars=0, context=CS_PHRYG)])
    assert a["notes"] == b["notes"]
    assert min(n["start_time"] for n in a["notes"]) >= 8.0


def test_selection_clips_notes_to_its_end(js):
    ctx = {**F_MINOR, "time_selection": {"start_time": 13.0, "end_time": 19.5}}  # 3.2.1 až 5.4.3, kus taktu
    r = run(js, [case("lead", bars=0, density=100, context=ctx)])[0]
    assert r["notes"]
    for n in r["notes"]:
        assert 13.0 <= n["start_time"] < 19.5 and n["start_time"] + n["duration"] <= 19.5 + 1e-9


def test_no_selection_starts_at_insert_marker(js):
    r = run(js, [case("kick", bars=2, context={**F_MINOR, "insert_marker_time": 16.0})])[0]
    assert min(n["start_time"] for n in r["notes"]) >= 16.0
    assert max(n["start_time"] for n in r["notes"]) < 24.0


def test_density_dial_moves_note_count(js):
    lo, hi = run(js, [case("lead", density=0, bars=4), case("lead", density=100, bars=4)])
    assert len(hi["notes"]) > len(lo["notes"])


def test_dice_sends_seed_number(js):
    (out,) = run(js, [], dice=True)["dice"]
    assert out[0] == 1 and 1 <= out[1] <= 999


def test_amxd_container_matches_template_layout():
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    data = B.amxd_bytes(B.build_patcher(B.js_source(model)))
    assert data[:12] == b"ampf\x04\x00\x00\x00nagg"
    assert data[12:24] == b"meta\x04\x00\x00\x00\x00\x00\x00\x00"
    assert data[24:28] == b"ptch"
    n = struct.unpack("<I", data[28:32])[0]
    body = data[32:]
    assert len(body) == n and body.endswith(b"\n\x00")
    patcher = json.loads(body[:-1].decode("utf-8"))["patcher"]
    assert patcher["project"]["amxdtype"] == 1851877223
    ids = {b["box"]["id"] for b in patcher["boxes"]}
    for ln in patcher["lines"]:
        assert ln["patchline"]["source"][0] in ids and ln["patchline"]["destination"][0] in ids
    names = [b["box"]["saved_attribute_attributes"]["valueof"]["parameter_longname"]
             for b in patcher["boxes"] if "saved_attribute_attributes" in b["box"]]
    assert len(names) == len(set(names))  # Live chce unikátní jména parametrů


def _by_start(notes):
    out = {}
    for n in notes:
        out.setdefault(n["start_time"], []).append(n)
    return dict(sorted(out.items()))


def test_reese_plays_long_notes(js):
    res = run(js, [case("reese", bars=4, seed=s) for s in (1, 2, 3, 4)])
    durs = sorted(n["duration"] for r in res for n in r["notes"])
    assert durs[len(durs) // 2] >= 1.0  # medián aspoň doba, v referencích ~1 doba, q3 3 doby


def test_legato_extremes(js):
    lo, hi = run(js, [case("reese", bars=4, seed=2, legato=0, density=100), case("reese", bars=4, seed=2, legato=100, density=100)])
    for r, overlap in ((lo, False), (hi, True)):
        groups = list(_by_start(r["notes"]).values())
        seen_overlap = False
        for a, b in zip(groups, groups[1:]):
            end = a[0]["start_time"] + a[0]["duration"]
            if overlap:
                if a[0]["pitch"] != b[0]["pitch"]:
                    seen_overlap |= end > b[0]["start_time"]
                else:
                    assert end <= b[0]["start_time"] + 1e-9  # stejná výška se nesmí překrýt
            else:
                assert end < b[0]["start_time"]  # mezera proti mazanici
        if overlap:
            assert seen_overlap


def test_voicing_chords_from_scale(js):
    allowed = {(5 + i) % 12 for i in F_MINOR["scale"]["scale_intervals"]}
    tri, sev = run(js, [case("reese", voicing=VOICES.index("Akord")), case("reese", voicing=VOICES.index("Akord 9"))])
    for r, size in ((tri, 3), (sev, 4)):
        for chord in _by_start(r["notes"]).values():
            assert len(chord) in (size, 2)  # 2 = chromatický tón mimo stupnici dostane jen kvintu
            if len(chord) == size:
                assert {n["pitch"] % 12 for n in chord} <= allowed


def test_builder_menus_match_js():
    src = (Path(__file__).parent / "npos_skeleton.js").read_text(encoding="utf-8")
    assert json.dumps(B.ROLE_LABELS, ensure_ascii=False).replace(", ", ",") in src.replace(", ", ",")
    assert json.dumps(B.VOICE_LABELS, ensure_ascii=False).replace(", ", ",") in src.replace(", ", ",")


def _sounding(notes, t):
    return {n["pitch"] % 12 for n in notes if n["start_time"] <= t < n["start_time"] + n["duration"]}


def test_shared_harmony_bass_follows_pad(js):
    # stejný seed = stejná progrese: dlouhé basové tóny a tóny na době leží v akordu, který hraje Pad
    for s in (1, 2, 3, 4, 5):
        pad, bass, reese = run(js, [case("harmony", seed=s, bars=4, density=10), case("bass", seed=s, bars=4),
                                    case("reese", seed=s, bars=4)])
        for line in (bass, reese):
            for n in line["notes"]:
                strong = abs((n["start_time"] * 4) % 4) < 1e-6 or n["duration"] >= 0.5
                chord = _sounding(pad["notes"], n["start_time"])
                if strong and chord:
                    assert n["pitch"] % 12 in chord, (s, n, chord)


def test_harmony_plan_ignores_knobs(js):
    # Hustota a Variace na Padu mění rytmus, ne akordy
    a, b = run(js, [case("harmony", seed=7, bars=4, density=10, variation=0), case("harmony", seed=7, bars=4, density=90, variation=90)])
    pcs = lambda r: {n["pitch"] % 12 for n in r["notes"]}
    assert pcs(a) == pcs(b)


def test_lead_answers_into_bass_gaps(js):
    for s in (1, 2, 3, 4):
        bass, lead = run(js, [case("bass", seed=s, bars=4, octave=0, voicing=0, legato=50),
                              case("lead", seed=s, bars=4, link=2)])
        busy = []
        for n in bass["notes"]:
            busy.append((n["start_time"] - 0.01, n["start_time"] + min(n["duration"], 0.5)))
        for n in lead["notes"]:
            assert not any(a <= n["start_time"] < b for a, b in busy), (s, n)


def test_free_link_keeps_old_independent_mode(js):
    a, b = run(js, [case("bass", seed=3, link=0), case("bass", seed=3, link=1)])
    assert a["notes"] and b["notes"]
