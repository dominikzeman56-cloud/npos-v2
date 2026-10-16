import json
import os
import random
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pytest  # noqa: E402

import analyze_fxp_host as fh  # noqa: E402
import rebuild_preset_indexes as rpi  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
BASS_LAZER_FXP = Path(os.environ.get("S1_BASS_LAZER_FXP") or
                      r"C:\Users\domin\Documents\Xfer\Serum 2 Presets\Presets\S1 Presets\REDPILL 21\TSP_REDPILL_Bass_lazer.fxp")
STATE = 172736  # velikost stavu, kterou host přijímá


def state(fill: int, wav: bytes = b"") -> bytes:
    """Stav požadované velikosti; volitelně s odkazem na wavetable (jako ho v něm nechává Serum 1)."""
    head = bytes([fill]) * 100 + (b"\0" + wav + b"\0" if wav else b"")
    return head + bytes([fill]) * (STATE - len(head))


def make_fxp(path: Path, name="Main Bass", st=None, kind=b"FPCh", fx_id=b"XfsX"):
    z = zlib.compress(st if st is not None else b"\0" * STATE)
    d = b"CcnK" + struct.pack(">I", 0) + kind + struct.pack(">I", 1) + fx_id + struct.pack(">II", 1, 1) + name.encode().ljust(28, b"\0") + struct.pack(">I", len(z)) + z
    path.write_bytes(d)
    return path


def P(**kw):
    """Hostovské parametry {klíč: {raw, text}} z dvojic klíč=(raw, text)."""
    return {k: {"raw": v[0], "text": v[1]} for k, v in kw.items()}


class FakeHost:
    """Náhrada pluginu: každému načtenému .fxp přiřadí parametry podle jeho jména v hlavičce, bez pedalboard."""

    def __init__(self, by_name: dict[str, dict]):
        self.by_name, self.loaded = by_name, None

    def load_fxp(self, fxp: bytes) -> None:
        self.loaded = fxp[28:56].split(b"\0", 1)[0].decode("latin-1")

    def read(self) -> dict:
        return self.by_name[self.loaded]


# ─── kodek a stav ──────────────────────────────────────────────────────────────────────────────────────────────

def _slow_encode(b: bytes) -> str:
    nbits, out = len(b) * 8, []
    for pos in range(0, nbits, 6):
        v = 0
        for k in range(6):
            bp = pos + k
            if bp < nbits and (b[bp // 8] >> (bp % 8)) & 1:
                v |= 1 << k
        out.append(fh._ALPH[v])
    return f"{len(b)}." + "".join(out)


def test_juce_base64_matches_bitwise_reference_and_roundtrips():
    rnd = random.Random(1)
    for n in (0, 1, 2, 3, 4, 5, 7, 100, 1001):
        b = bytes(rnd.randrange(256) for _ in range(n))
        assert fh.juce_b64_encode(b) == _slow_encode(b)
        assert fh.juce_b64_decode(fh.juce_b64_encode(b)) == b


def test_juce_base64_rejects_garbage():
    for bad in ("nic", "10.AA", "3.AB!D", "١٢.AAAA"):   # bez tečky, krátké, cizí znak, nearabské číslice
        with pytest.raises(ValueError):
            fh.juce_b64_decode(bad)


def _base_state(chunk: bytes = b"x\x01old") -> bytes:
    xml = f'<?xml version="1.0" encoding="UTF-8"?> <VST3PluginState><IComponent>{fh.juce_b64_encode(chunk)}</IComponent></VST3PluginState>'
    body = xml.encode() + b"\0"
    return b"VC2!" + struct.pack("<I", len(body)) + body


def test_state_from_fxp_replaces_component_with_fxp_chunk(tmp_path):
    z = zlib.compress(b"preset-state")
    fxp = make_fxp(tmp_path / "a.fxp", st=b"preset-state").read_bytes()
    out = fh.state_from_fxp(_base_state(), fxp)
    assert out[:4] == b"VC2!" and struct.unpack_from("<I", out, 4)[0] == len(out) - 8 and out.endswith(b"\0")
    comp = fh._COMPONENT.search(out[8:].decode()).group(1)
    assert fh.juce_b64_decode(comp) == z


def test_state_from_fxp_rejects_foreign_input(tmp_path):
    fxp = make_fxp(tmp_path / "a.fxp").read_bytes()
    with pytest.raises(ValueError):
        fh.state_from_fxp(b"nope" * 5, fxp)
    with pytest.raises(ValueError):
        fh.state_from_fxp(_base_state(), make_fxp(tmp_path / "bank.fxp", kind=b"FBCh").read_bytes())
    with pytest.raises(ValueError):
        fh.state_from_fxp(_base_state(), b"garbage" * 20)


# ─── host (s náhradním pluginem) ───────────────────────────────────────────────────────────────────────────────

class _Param:
    def __init__(self, raw=None, text="x"):
        if raw is not None:
            self.raw_value = raw
        self.string_value = text


class _Plugin:
    def __init__(self, base: bytes):
        self.log, self._state = [], base

    @property
    def raw_state(self):
        return self._state

    @raw_state.setter
    def raw_state(self, v):
        self.log.append(v)
        self._state = v


class _Host(fh.S1Host):
    """S1Host bez pedalboard: parametry se berou ze slovníku podle toho, jaký stav je právě v pluginu."""

    def __init__(self, base: bytes, states: dict[bytes, dict]):
        self.plugin, self.base, self.states = _Plugin(base), base, states
        self.init = states[base]

    def read(self):
        return self.states.get(self.plugin.raw_state, self.init)   # neznámý stav = plugin ho nepřijal, zůstává výchozí


def test_s1host_read_tolerates_params_without_raw_value():
    h = fh.S1Host.__new__(fh.S1Host)
    h.params = {"macro_1": _Param(None, "0"), "a_vol": _Param(0.123456789, " 12%")}
    h.keys = ["macro_1", "a_vol"]
    assert h.read() == {"macro_1": {"raw": None, "text": "0"}, "a_vol": {"raw": 0.12346, "text": " 12%"}}


def test_s1host_load_resets_first_and_rejects_a_state_the_plugin_ignored(tmp_path):
    base = _base_state()
    fxp = make_fxp(tmp_path / "a.fxp", st=b"abc").read_bytes()
    loaded = fh.state_from_fxp(base, fxp)
    h = _Host(base, {base: P(a_vol=(0.75, "75")), loaded: P(a_vol=(1.0, "100"))})
    h.plugin._state = loaded                                  # předchozí preset
    h.load_fxp(fxp)
    assert h.plugin.log[0] == base and h.plugin.log[1] == loaded and h.read()["a_vol"]["raw"] == 1.0   # nejdřív reset

    ignoring = _Host(base, {base: P(a_vol=(0.75, "75"))})     # stav z .fxp plugin nezná → zůstane výchozí
    with pytest.raises(RuntimeError, match="nepřijal"):
        ignoring.load_fxp(fxp)


# ─── měření ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_measure_reads_osc_filter_fx_and_leaves_modulation_unknown():
    params = P(osc_a_on=(1.0, "on"), osc_b_on=(1.0, "on"), osc_n_on=(0.0, "off"), osc_s_on=(1.0, "on"),
               a_vol=(1.0, "100%"), b_vol=(0.0, "0% (-oo dB)"), a_unison=(1.0, "16"), b_unison=(0.0, "1"),
               a_unidet=(0.68, "0.46"), b_unidet=(0.5, "0.25"), a_octave_oct=(0.5, "0"), b_octave_oct=(0.5, "0"),
               a_fine_cents=(0.5, "0"), b_fine_cents=(0.5, "0"), warposca=(0.78, "FM (from B)"), warposcb=(0.0, "Off"),
               filter_on=(1.0, "on"), fil_cutoff_hz=(0.127194, "22"), fil_reso=(0.35029, "35"), fil_driv=(0.25, "25"),
               dist_enable=(1.0, "on"), dist_mode=(0.26, "Diode 2"), rev_enable=(1.0, "on"), eq_enable=(0.0, "off"),
               hyp_enable=(1.0, "on"), comp_enable=(1.0, "on"), cmpmbnd=(1.0, "MultBand"),
               mod_1_amt=(0.625, "25"), mod_2_amt=(0.5, "0"), mod10_amt=(1.0, "100"), mod11_amt=(0.0, "-100"),
               mod12_amt=(0.50002, "0"))
    cues, feats, chain = fh.measure(params)
    assert cues["active_osc"] == 2 and cues["sub"] is True and cues["noise"] is False and cues["max_unison"] == 16
    assert cues["cross_warp"] == ["FM (from B)"] and cues["warp_modes"] == ["FM (from B)"]
    assert cues["zero_vol_osc"] == 1 and cues["fx_count"] == 4
    assert cues["mod_slots"] == 3                        # amount 0 (i zaokrouhlený na 0) se nepočítá, -100 ano
    assert cues["lfo_to_filter"] is None and cues["silent_mod_osc"] is None and cues["mono"] is None
    assert feats["unison_max"] == 16 and feats["unison_sum"] == 17 and feats["detune_max"] == 0.46
    assert feats["warp_slots"] == 1 and feats["filters_on"] == 1 and feats["filter_freq"] == 0.1272
    assert feats["filter_reso"] == 35.029 and feats["filter_drive"] == 25.0         # procenta 0–100 jako ve Serum 2
    assert feats["fx_distortion"] == 1 and feats["fx_reverb"] == 1 and feats["fx_eq"] == 0 and feats["fx_bode"] == 0
    assert feats["fx_hyper"] == 1 and feats["fx_comp"] == 1
    assert chain == ["Comp (MultBand)", "Distortion (Diode 2)", "HyperD", "Reverb"]   # abecedně, názvy jako ve Serum 2
    for k in ("mod_lfo", "mod_env", "mod_macro", "mod_to_osc", "mod_to_filter", "lfo_curves", "mono"):
        assert feats[k] is None                           # zdroj/cíl modulace a křivky z hostu nejsou


def test_cross_warp_needs_enabled_source_and_excludes_single_osc_warps():
    base = dict(osc_a_on=(1.0, "on"), osc_b_on=(0.0, "off"), osc_n_on=(0.0, "off"), osc_s_on=(0.0, "off"))
    off_source = fh.measure(P(**base, warposca=(0.5, "FM (from B)")))[0]           # FM z vypnutého B
    assert off_source["cross_warp"] == [] and off_source["warp_modes"] == ["FM (from B)"]
    bend = fh.measure(P(**base, warposca=(0.5, "Bend +")))[0]
    assert bend["cross_warp"] == [] and bend["warp_modes"] == ["Bend +"]            # jednooscilátorový warp
    noise = fh.measure(P(**{**base, "osc_n_on": (1.0, "on")}, warposca=(0.5, "FM (Noise)")))[0]
    assert noise["cross_warp"] == ["FM (Noise)"]


def test_measure_filter_off_and_fine_spread():
    params = P(osc_a_on=(1.0, "on"), osc_b_on=(1.0, "on"), a_vol=(0.8, "x"), b_vol=(0.8, "x"), a_octave_oct=(0.5, "0"),
               b_octave_oct=(0.5, "0"), a_fine_cents=(0.4, "-20"), b_fine_cents=(0.6, "20"), filter_on=(0.0, "off"))
    cues, feats, _ = fh.measure(params)
    assert cues["fine_spread"] is True and feats["filters_on"] == 0 and feats["filter_freq"] is None
    assert feats["detune_max"] == 0                      # unison 1 nemá detune


def test_measure_ignores_nonfinite_display_text():
    cues, feats, _ = fh.measure(P(osc_a_on=(1.0, "on"), a_unison=(0.0, "inf"), a_unidet=(0.5, "nan")))
    assert cues["max_unison"] == 1 and feats["detune_max"] == 0


def test_feature_keys_equal_serum2_feature_keys():
    assert list(fh.measure({})[1]) == list(rpi.features({}))


def test_propose_uses_name_rules_and_only_provable_archetypes():
    fm = {"cross_warp": ["FM (from B)"], "warp_modes": ["FM (from B)"], "fine_spread": False, "max_unison": 1, "noise": False}
    assert fh.propose("Main Bass", fm)[:2] == ("body", "fm-distorted-body")
    spread = {"cross_warp": [], "warp_modes": [], "fine_spread": True, "max_unison": 1, "noise": False}
    assert fh.propose("Best Reese", spread)[:2] == ("body", "detuned-unison-reese")
    plain = {"cross_warp": [], "warp_modes": [], "fine_spread": False, "max_unison": 1, "noise": False}
    func, arch, why = fh.propose("Reese Heavy", plain)
    assert (func, arch) == ("body", "unclassified") and "neznámý" in why[-1]
    assert fh.propose("Sub Bass", plain)[:2] == ("sub", "clean-sub-sine")
    assert fh.propose("TK - 12", plain)[:2] == ("other", "unclassified")


def test_clean_sub_sine_needs_measured_support():
    for dirty in ({"warp_modes": ["Bend +"]}, {"max_unison": 7}, {"noise": True}):
        c = {"cross_warp": [], "warp_modes": [], "fine_spread": False, "max_unison": 1, "noise": False} | dirty
        func, arch, why = fh.propose("Sub Bass", c)
        assert (func, arch) == ("sub", "unclassified") and "nepotvrzují" in why[-1]


# ─── dávka s náhradním hostem (bez pluginu) ────────────────────────────────────────────────────────────────────

SIMPLE = P(osc_a_on=(1.0, "on"), osc_b_on=(0.0, "off"), a_vol=(1.0, "100"), filter_on=(1.0, "on"), fil_cutoff_hz=(0.5, "425"),
           fil_reso=(0.1, "10"), fil_driv=(0.0, "0"))


def test_run_builds_rows_ids_dumps_and_keeps_wavetable_names_out_of_rows(tmp_path):
    (tmp_path / "pack" / "grp").mkdir(parents=True)
    make_fxp(tmp_path / "pack" / "grp" / "Main Bass.fxp", name="Main Bass", st=state(1, b"Paid Pack/Tables/DNA.wav"))
    make_fxp(tmp_path / "pack" / "grp" / "Best Reese.fxp", name="Best Reese", st=state(2))
    make_fxp(tmp_path / "pack" / "grp" / "zz.fxp", name="Main Bass", st=state(1, b"Paid Pack/Tables/DNA.wav"))   # stejný obsah
    make_fxp(tmp_path / "pack" / "grp" / "Small.fxp", name="Small", st=b"\3" * 100)                             # neznámá velikost stavu
    host = FakeHost({"Main Bass": SIMPLE, "Best Reese": SIMPLE})
    idx, feats, bad = fh.run([tmp_path / "pack"], "s1-test", host, dump_dir=tmp_path / "dump", log=lambda *_: None)
    assert [r["name"] for r in idx] == ["Best Reese", "Main Bass"] and len(feats) == 2
    r = next(r for r in idx if r["name"] == "Main Bass")
    assert r["id"] == "s1-test-grp-main-bass" and r["group"] == "grp" and r["cues_basis"] == "preset_file"
    assert r["reader"] == "serum1_host" and r["confidence"] == "hypothesis" and r["fx_order"] == "unknown" and "convert" not in r
    assert r["role"] == "bass" and r["container"]["sha256"]
    assert "wavs" not in r["container"] and r["container"]["wav_count"] == 1 and ".wav" not in json.dumps(r)   # jména jen v dumpu
    f = next(f for f in feats if f["id"] == r["id"])
    assert f["basis"] == "preset_file" and f["reader"] == "serum1_host" and f["features"]["filter_freq"] == 0.5
    assert len(bad) == 1 and "Small.fxp" in bad[0] and "velikost stavu" in bad[0]
    dump = json.loads((tmp_path / "dump" / f"{r['id']}.json").read_text(encoding="utf-8"))
    assert dump["host"]["a_vol"] == [1.0, "100"] and any(w.endswith("DNA.wav") for w in dump["container"]["wavs"])


def test_run_rejects_non_serum1_fxp(tmp_path):
    (tmp_path / "p").mkdir()
    make_fxp(tmp_path / "p" / "other.fxp", name="Other", fx_id=b"AbCd")
    idx, _, bad = fh.run([tmp_path / "p"], "s1-test", FakeHost({"Other": SIMPLE}), log=lambda *_: None)
    assert not idx and len(bad) == 1 and "není Serum 1" in bad[0]


def test_run_makes_colliding_ids_unique(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    make_fxp(tmp_path / "a" / "x.fxp", name="Same", st=state(1))
    make_fxp(tmp_path / "b" / "x.fxp", name="Same", st=state(2))
    idx, _, bad = fh.run([tmp_path / "a", tmp_path / "b"], "s1-test", FakeHost({"Same": SIMPLE}), log=lambda *_: None)
    ids = [r["id"] for r in idx]
    assert not bad and len(set(ids)) == 2 and all(i.startswith("s1-test-x-") for i in ids)


def test_run_match_index_pins_ids_order_and_reports_missing(tmp_path):
    (tmp_path / "p").mkdir()
    make_fxp(tmp_path / "p" / "one.fxp", name="One", st=state(1))
    make_fxp(tmp_path / "p" / "two.fxp", name="Two", st=state(2))
    sha = {n: fh.fx.read_fxp(tmp_path / "p" / f"{n}.fxp")["sha256"] for n in ("one", "two")}
    old = [{"id": "keep-two", "name": "Two", "group": "G", "file": "two.fxp", "container": {"sha256": sha["two"]}},
           {"id": "keep-one", "name": "One", "group": "", "file": "one.fxp", "container": {"sha256": sha["one"]}},
           {"id": "gone", "name": "Gone", "group": "", "file": "gone.fxp", "container": {"sha256": "0" * 16}}]
    idx, _, bad = fh.run([tmp_path / "p"], "s1-test", FakeHost({"One": SIMPLE, "Two": SIMPLE}), match=old, log=lambda *_: None)
    assert [r["id"] for r in idx] == ["keep-two", "keep-one"] and idx[0]["group"] == "G"
    assert len(bad) == 1 and "gone" in bad[0]


def test_run_survives_failure_in_host_or_measurement(tmp_path):
    (tmp_path / "p").mkdir()
    make_fxp(tmp_path / "p" / "ok.fxp", name="Ok", st=state(1))
    make_fxp(tmp_path / "p" / "boom.fxp", name="Boom", st=state(2))
    make_fxp(tmp_path / "p" / "bad.fxp", name="Bad", st=state(3))
    weird = {"osc_a_on": None}                                                            # shodí měření, ne host
    idx, _, bad = fh.run([tmp_path / "p"], "s1-test", FakeHost({"Ok": SIMPLE, "Bad": weird}), log=lambda *_: None)   # Boom → KeyError
    assert [r["name"] for r in idx] == ["Ok"] and len(bad) == 2 and any("boom.fxp" in b for b in bad)


# ─── --by-folder: zdroje po složkách ───────────────────────────────────────────────────────────────────────────

@pytest.fixture
def s1root(tmp_path):
    root = tmp_path / "S1 Presets"
    for d in ("Alfa", "beta", "Píčius", "Done", "gpt"):
        (root / d).mkdir(parents=True)
    make_fxp(root / "Alfa" / "a1.fxp", name="Alfa One", st=state(1))
    (root / "Alfa" / "sub").mkdir()
    make_fxp(root / "Alfa" / "sub" / "a2.fxp", name="Alfa Two", st=state(2))
    make_fxp(root / "beta" / "b1.fxp", name="Alfa One", st=state(1))              # stejný obsah jako Alfa/a1 → duplikát
    make_fxp(root / "beta" / "b2.fxp", name="Beta Two", st=state(3))
    make_fxp(root / "Píčius" / "p1.fxp", name="Pi", st=state(4))
    make_fxp(root / "Done" / "d1.fxp", name="Done One", st=state(5))              # už zapsaný jinde → vynechat
    make_fxp(root / "gpt" / "g1.fxp", name="G", st=state(6))                      # vynechaná složka
    make_fxp(root / "loose.fxp", name="Loose", st=state(7))
    return root


HOST = FakeHost({n: SIMPLE for n in ("Alfa One", "Alfa Two", "Beta Two", "Pi", "Done One", "G", "Loose")})


def test_run_skip_and_stats(tmp_path):
    (tmp_path / "p").mkdir()
    make_fxp(tmp_path / "p" / "one.fxp", name="One", st=state(1))
    make_fxp(tmp_path / "p" / "two.fxp", name="Two", st=state(2))
    skip = {fh.fx.read_fxp(tmp_path / "p" / "one.fxp")["sha256"]}
    stats = {}
    idx, _, _ = fh.run([tmp_path / "p"], "s1-x", FakeHost({"One": SIMPLE, "Two": SIMPLE}), skip=skip, stats=stats, log=lambda *_: None)
    assert [r["name"] for r in idx] == ["Two"] and stats == {"files": 2, "duplicates": 1}
    assert len(skip) == 2                                                          # doplněno o zpracované


def test_by_folder_splits_sources_dedupes_across_folders_and_writes_outputs(s1root, tmp_path):
    done_sha = fh.fx.read_fxp(s1root / "Done" / "d1.fxp")["sha256"]
    out = tmp_path / "out"
    summary, bad = fh.by_folder(s1root, HOST, "s1-", out, {"gpt"}, {done_sha}, log=lambda *_: None)
    assert not bad
    assert [(s["id"], s["presets"], s["duplicates"]) for s in summary] == [
        ("s1-alfa", 2, 0), ("s1-beta", 1, 1), ("s1-picius", 1, 0), ("s1-root", 1, 0)]   # Done: jen duplikáty → bez zdroje
    alfa = [json.loads(line) for line in (out / "fxp" / "s1-alfa.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["group"] for r in alfa} == {"", "sub"} and all(r["source_id"] == "s1-alfa" for r in alfa)
    assert (out / "features" / "s1-alfa.jsonl").exists() and (out / "_local" / "s1-alfa-host").is_dir()
    assert not (out / "fxp" / "s1-done.jsonl").exists() and not (out / "fxp" / "s1-gpt.jsonl").exists()


def test_by_folder_dry_run_writes_nothing(s1root, tmp_path):
    summary, _ = fh.by_folder(s1root, HOST, "s1-", tmp_path / "out", {"gpt"}, set(), log=lambda *_: None, write=False)
    assert sum(s["presets"] for s in summary) == 6 and not (tmp_path / "out").exists()


def test_by_folder_refuses_colliding_source_ids(tmp_path):
    root = tmp_path / "r"
    for d in ("Abc", "ABC!"):
        (root / d).mkdir(parents=True)
    make_fxp(root / "Abc" / "x.fxp", name="Alfa One", st=state(1))
    make_fxp(root / "ABC!" / "y.fxp", name="Alfa One", st=state(2))
    with pytest.raises(ValueError, match="s1-abc"):
        fh.by_folder(root, HOST, "s1-", tmp_path / "out", set(), set(), log=lambda *_: None)


def test_source_entry_has_no_author_and_no_wavetable_or_parameter_claims():
    item = {"id": "s1-alfa", "folder": "Alfa", "files": 12, "presets": 9, "duplicates": 3, "bad": 1}
    e = fh.source_entry(item, "2026-10-16")
    assert e["author"] == "bez autora" and e["redistribution"] == "none" and e["basis"] == "preset_file"
    assert e["title"] == "Alfa — Serum 1 presety (.fxp; složka Alfa)" and e["verified_on"] == "2026-10-16"
    assert "12 .fxp" in e["notes"] and "9 po deduplikaci" in e["notes"] and "1 nečitelných" in e["notes"]
    assert "Autorství nepotvrzeno" in e["notes"]
    root = fh.source_entry({**item, "id": "s1-root", "folder": "(root)"}, "2026-10-16")
    assert root["title"] == "Serum 1 presety (.fxp; soubory přímo ve složce S1 Presets)"


def test_main_by_folder_writes_summary_and_sources(s1root, tmp_path, monkeypatch):
    monkeypatch.setattr(fh, "S1Host", lambda plugin=None: HOST)
    done = tmp_path / "done.jsonl"
    done.write_text(json.dumps({"container": {"sha256": fh.fx.read_fxp(s1root / "Done" / "d1.fxp")["sha256"]}}) + "\n", encoding="utf-8")
    rc = fh.main(["--by-folder", str(s1root), "--out-dir", str(tmp_path / "out"), "--skip-folder", "gpt", "--exclude-index", str(done),
                  "--summary", str(tmp_path / "sum.json"), "--sources-out", str(tmp_path / "src.jsonl")])
    assert rc == 0
    assert [s["id"] for s in json.loads((tmp_path / "sum.json").read_text(encoding="utf-8"))] == ["s1-alfa", "s1-beta", "s1-picius", "s1-root"]
    assert len((tmp_path / "src.jsonl").read_text(encoding="utf-8").splitlines()) == 4
    assert fh.main(["--by-folder", str(tmp_path / "nope")]) == 2
    assert fh.main(["--by-folder", str(s1root), "--exclude-index", str(tmp_path / "nope.jsonl")]) == 2


# ─── main(): bezpečný zápis ────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def pack(tmp_path, monkeypatch):
    (tmp_path / "p").mkdir()
    for i, n in enumerate(("One", "Two", "Three")):
        make_fxp(tmp_path / "p" / f"{n}.fxp", name=n, st=state(i + 1))
    monkeypatch.setattr(fh, "S1Host", lambda plugin=None: FakeHost({"One": SIMPLE, "Two": SIMPLE, "Three": SIMPLE}))
    return tmp_path


def _args(pack, out, *extra):
    return [str(pack / "p"), "--source-id", "s1-test", "--out-index", str(out), "--out-features", str(pack / "f.jsonl"), *extra]


def test_main_writes_atomically_and_exits_zero(pack):
    out = pack / "idx.jsonl"
    assert fh.main(_args(pack, out)) == 0
    assert len(out.read_text(encoding="utf-8").splitlines()) == 3 and not list(pack.glob("*.tmp"))


def test_main_does_not_shrink_or_wipe_the_pinned_index(pack):
    out = pack / "idx.jsonl"
    fh.main(_args(pack, out))
    before = out.read_text(encoding="utf-8")
    assert fh.main(_args(pack, out, "--match-index", str(out), "--limit", "1")) == 2          # --limit by index zmenšil
    (pack / "empty").mkdir()
    assert fh.main([str(pack / "empty"), "--source-id", "s1-test", "--match-index", str(out), "--out-index", str(out)]) == 1   # nic nenalezeno
    assert out.read_text(encoding="utf-8") == before
    (pack / "p" / "Three.fxp").unlink()
    assert fh.main(_args(pack, out, "--match-index", str(out))) == 1                           # chybí řádek → nezapisuje
    assert out.read_text(encoding="utf-8") == before
    assert fh.main(_args(pack, out, "--match-index", str(out), "--allow-partial")) == 1        # zapíše, ale hlásí chybu (chybějící soubor)
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2


def test_main_exit_codes_for_bad_input_and_missing_plugin(pack, monkeypatch):
    assert fh.main([str(pack / "nope"), "--source-id", "s1-test"]) == 2
    assert fh.main([str(pack / "p"), "--source-id", "s1-test", "--match-index", str(pack / "nope.jsonl")]) == 2

    def no_plugin(plugin=None):
        raise RuntimeError("chybí pedalboard")
    monkeypatch.setattr(fh, "S1Host", no_plugin)
    assert fh.main([str(pack / "p"), "--source-id", "s1-test", "--out-index", str(pack / "i.jsonl")]) == 2
    assert not (pack / "i.jsonl").exists()


def test_main_returns_nonzero_when_some_presets_fail(pack, monkeypatch):
    monkeypatch.setattr(fh, "S1Host", lambda plugin=None: FakeHost({"One": SIMPLE, "Two": SIMPLE}))   # Three → KeyError
    out = pack / "idx.jsonl"
    assert fh.main(_args(pack, out)) == 1
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2


# ─── zapsaná data (bez pluginu) ────────────────────────────────────────────────────────────────────────────────

S2_FEATURE_KEYS = list(rpi.features({}))


@pytest.mark.parametrize("source_id", ["s1-teddy-killerz", "s1-burr-oak", "s1-redpill"])
def test_committed_s1_rows_are_consistent(source_id):
    fxp = REPO / "data" / "presets" / "fxp" / f"{source_id}.jsonl"
    feats = REPO / "data" / "presets" / "features" / f"{source_id}.jsonl"
    if not fxp.exists() or not feats.exists():
        pytest.skip("index Serum 1 pro tenhle pack není v repu")
    idx = [json.loads(line) for line in fxp.read_text(encoding="utf-8").splitlines()]
    ft = [json.loads(line) for line in feats.read_text(encoding="utf-8").splitlines()]
    ids = [r["id"] for r in idx]
    assert len(set(ids)) == len(ids) and ids == [f["id"] for f in ft]
    for r, f in zip(idx, ft):
        assert r["source_id"] == f["source_id"] == source_id and r["confidence"] == f["confidence"] == "hypothesis"
        assert r["cues_basis"] == f["basis"] == "preset_file" and r["reader"] == f["reader"] == "serum1_host"
        assert list(f["features"]) == S2_FEATURE_KEYS
        assert r["function"] == f["function"] and r["role"] == f["role"] and r["archetype"] == f["archetype"]
        assert r["cues"]["lfo_to_filter"] is None and r["cues"]["silent_mod_osc"] is None and r["fx_order"] == "unknown"
        assert "wavs" not in r["container"] and ".wav" not in json.dumps(r).lower()


# ─── skutečné Serum 1 (přeskočí se, když chybí pedalboard / plugin / zdrojový soubor) ──────────────────────────

def _host_or_skip():
    pytest.importorskip("pedalboard")
    plugin = os.environ.get("SERUM1_VST3") or fh.DEFAULT_PLUGIN
    if not Path(plugin).exists():
        pytest.skip(f"Serum 1 VST3 nenalezeno: {plugin}")
    return fh.S1Host(plugin)


def test_host_reads_bass_lazer_like_the_serum2_conversion():
    """Pár TSP_REDPILL_Bass_lazer: čtení Serum 1 hostem vs. převod v Serum 2 (data/presets/features/s1-redpill-converted.jsonl)."""
    if not BASS_LAZER_FXP.exists():
        pytest.skip("zdrojové .fxp není na tomhle počítači (cesta jde změnit přes S1_BASS_LAZER_FXP)")
    host = _host_or_skip()
    host.load_fxp(BASS_LAZER_FXP.read_bytes())
    base = {"id": "x", "source_id": "t", "name": "REDPILL_Bass_lazer", "group": "", "file": "a.fxp", "container": {}}
    index, feature = fh.build_rows(host.read(), base)
    ref = json.loads((REPO / "data" / "presets" / "features" / "s1-redpill-converted.jsonl").read_text(encoding="utf-8").splitlines()[0])["features"]
    same = ["osc_on", "unison_max", "unison_sum", "detune_max", "warp_slots", "noise_on", "sub_on", "filters_on", "filter_freq",
            "filter_reso", "fx_count", "mod_slots"] + [k for k in ref if k.startswith("fx_")]
    for k in same:
        assert feature["features"][k] == ref[k], k
    assert index["cues"]["cross_warp"] == ["FM (from B)"]   # Serum 2 převádí FM (from B) na kPD_OSC


def test_host_rejects_a_state_it_cannot_load(tmp_path):
    host = _host_or_skip()
    with pytest.raises(RuntimeError, match="nepřijal"):
        host.load_fxp(make_fxp(tmp_path / "zeros.fxp", st=b"\0" * STATE).read_bytes())
