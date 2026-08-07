"""
feature_vector.py — Serum 2 preset feature-vector codec (M1.1).

Bidirectional mapping between a decoded preset's cbor_dict and a fixed-length
float32 numpy vector. Enables:
  - comparison / clustering of presets
  - training data for future statistical / neural generators (M2/M3)
  - reproducible logging of generated presets

Design constraints (from corpus inspection):
  - plainParams may be the literal string 'default' when nothing is set.
  - Categoricals (warp menu, filter type, FX type) are one-hot encoded.
  - Unknown categorical values collapse to an explicit 'other' slot (no crash).
  - Output is fixed-length float32; deterministic for identical input.

Schema (VECTOR_DIM total):

  Oscillators (i = 0..2, 3 osc):
    per osc: octave(1) volume(1) unison(1) detune(1) enable(1)        = 5
             warp one-hot (WARP_MENUS + other)                         = len(WARP_MENUS)+1
  VoiceFilters (i = 0..1, 2 filters):
    per filter: freq(1) reso(1) drive(1) enable(1)                     = 4
                type one-hot (FILTER_TYPES + other)                    = len(FILTER_TYPES)+1
  FX chain (MAX_FX slots):
    per slot: type one-hot (FX_TYPES + empty)                          = 17
              drive(1) wet(1) freq(1)                                  = 3
"""
from __future__ import annotations

from typing import Any

import numpy as np

from neuroman.tools.serum_preset import FX_MODULE_NAMES, FX_TYPES

# ─── Categorical vocabularies (from 400-preset corpus scan) ──────────────
# Warp menus observed on WTOsc sub-modules.
WARP_MENUS: tuple[str, ...] = (
    'kPD_OSC', 'kSync', 'kBendPos', 'kPD_SUB', 'kDistTube', 'kFM_OSC', 'kFM_SUB',
    'kPWM', 'kDistSoftSat', 'kFM_OSC2', 'kBendNeg', 'kBendPosNeg', 'kPD_OSC2',
    'kFM_NOISE', 'kAM_OSC',
)
# VoiceFilter type codes observed in the corpus.
FILTER_TYPES: tuple[str, ...] = (
    'MgL18', 'MgL24', 'LadderEMS', 'H24', 'LadderMg', 'H12', 'LadderAcid', 'H18',
    'MgL6', 'Diffuser', 'DirtyMg', 'LH12', 'Comb2', 'Reverb1', 'CombP', 'L24',
    'Wsp', 'BandReject', 'L18', 'ExpBPF',
)

NUM_OSC = 3
NUM_FILTERS = 2
MAX_FX = 6

_PER_OSC = 5 + len(WARP_MENUS) + 1        # warp + 'other'
_PER_FILTER = 4 + len(FILTER_TYPES) + 1   # type + 'other'
_FX_TYPES_COUNT = 16
_PER_FX = (_FX_TYPES_COUNT + 1) + 3       # type one-hot incl 'empty' + drive/wet/freq

VECTOR_DIM = NUM_OSC * _PER_OSC + NUM_FILTERS * _PER_FILTER + MAX_FX * _PER_FX


# ─── Schema layout helpers ───────────────────────────────────────────────


def _layout() -> dict[str, list[tuple[int, int]]]:
    """Return {(category, index): [(start, end), ...]} slice map."""
    slices: dict[str, list[tuple[int, int]]] = {}
    off = 0
    slices['osc'] = []
    for _ in range(NUM_OSC):
        slices['osc'].append((off, off + _PER_OSC)); off += _PER_OSC
    slices['filter'] = []
    for _ in range(NUM_FILTERS):
        slices['filter'].append((off, off + _PER_FILTER)); off += _PER_FILTER
    slices['fx'] = []
    for _ in range(MAX_FX):
        slices['fx'].append((off, off + _PER_FX)); off += _PER_FX
    return slices


_LAYOUT = _layout()

# Normalization ranges (min, max) for continuous params. Values outside are clipped.
_RANGES = {
    'octave': (-3.0, 3.0),
    'volume': (0.0, 1.0),
    'unison': (1.0, 16.0),
    'detune': (0.0, 1.0),
    'enable': (0.0, 1.0),
    'freq': (0.0, 1.0),
    'reso': (0.0, 100.0),
    'drive': (0.0, 100.0),
    'fx_drive': (0.0, 100.0),
    'fx_wet': (0.0, 100.0),
    'fx_freq': (0.0, 1.0),
}


def _norm(val: float, key: str) -> float:
    lo, hi = _RANGES[key]
    if hi == lo:
        return 0.0
    val = max(lo, min(hi, float(val)))
    return (val - lo) / (hi - lo)


def _denorm(n: float, key: str) -> float:
    lo, hi = _RANGES[key]
    n = max(0.0, min(1.0, float(n)))
    return lo + n * (hi - lo)


def _onehot_index(value: str | None, vocab: tuple[str, ...]) -> int:
    """Return index into vocab+1 (last = 'other'/unknown). None -> last too."""
    if value is None:
        return len(vocab)  # treat absent as 'other'
    try:
        return vocab.index(value)
    except ValueError:
        return len(vocab)


# ─── Public codec API ────────────────────────────────────────────────────


def _pp(module: dict[str, Any] | None) -> dict[str, Any]:
    """Return plainParams as dict, tolerating 'default' string / missing."""
    if not isinstance(module, dict):
        return {}
    pp = module.get('plainParams')
    if not isinstance(pp, dict):
        return {}
    return pp


def to_feature_vector(cbor_dict: dict[str, Any]) -> np.ndarray:
    """Encode a decoded preset's cbor_dict into a fixed float32 vector."""
    vec = np.zeros(VECTOR_DIM, dtype=np.float32)

    # Oscillators
    for i, (s, e) in enumerate(_LAYOUT['osc']):
        osc = cbor_dict.get(f'Oscillator{i}')
        pp = _pp(osc)
        vec[s + 0] = _norm(pp.get('kParamOctave', 0.0), 'octave')
        vec[s + 1] = _norm(pp.get('kParamVolume', 0.0), 'volume')
        vec[s + 2] = _norm(pp.get('kParamUnison', 1.0), 'unison')
        vec[s + 3] = _norm(pp.get('kParamDetune', 0.0), 'detune')
        vec[s + 4] = _norm(pp.get('kParamEnable', 0.0), 'enable')
        warp = None
        wto = osc.get(f'WTOsc{i}') if isinstance(osc, dict) else None
        if isinstance(wto, dict):
            warp = _pp(wto).get('kParamWarpMenu')
        vec[s + 5 + _onehot_index(warp, WARP_MENUS)] = 1.0

    # Voice filters
    for i, (s, e) in enumerate(_LAYOUT['filter']):
        vf = cbor_dict.get(f'VoiceFilter{i}')
        pp = _pp(vf)
        vec[s + 0] = _norm(pp.get('kParamFreq', 0.0), 'freq')
        vec[s + 1] = _norm(pp.get('kParamReso', 0.0), 'reso')
        vec[s + 2] = _norm(pp.get('kParamDrive', 0.0), 'drive')
        vec[s + 3] = _norm(pp.get('kParamEnable', 0.0), 'enable')
        vec[s + 4 + _onehot_index(pp.get('kParamType'), FILTER_TYPES)] = 1.0

    # FX chain (FXRack0 only — MAIN rack; BUS racks ignored for M1)
    fxr = cbor_dict.get('FXRack0')
    fx_list = fxr.get('FX', []) if isinstance(fxr, dict) else []
    for slot, (s, e) in enumerate(_LAYOUT['fx']):
        if slot >= len(fx_list):
            # empty slot: type 'empty' = last index of FX one-hot
            vec[s + _FX_TYPES_COUNT] = 1.0
            continue
        item = fx_list[slot]
        tid = item.get('type')
        if isinstance(tid, int) and 0 <= tid < _FX_TYPES_COUNT:
            vec[s + tid] = 1.0
        else:
            vec[s + _FX_TYPES_COUNT] = 1.0
        mod_key = next((k for k in item if k.startswith('FX') and k != 'FX'), None)
        fx_pp = _pp(item.get(mod_key) if mod_key else None)
        vec[s + _FX_TYPES_COUNT + 1] = _norm(fx_pp.get('kParamDrive', 0.0), 'fx_drive')
        vec[s + _FX_TYPES_COUNT + 2] = _norm(fx_pp.get('kParamWet', 0.0), 'fx_wet')
        vec[s + _FX_TYPES_COUNT + 3] = _norm(fx_pp.get('kParamFreq', 0.0), 'fx_freq')

    return vec


def from_feature_vector(vec: np.ndarray) -> dict[str, Any]:
    """Decode a vector back into a {params, fx_chain} dict compatible with build_preset."""
    if len(vec) != VECTOR_DIM:
        raise ValueError(f'Expected vector of length {VECTOR_DIM}, got {len(vec)}')
    vec = np.asarray(vec, dtype=np.float32)
    params: dict[str, dict[str, Any]] = {}
    fx_chain: list[dict] = []

    # Oscillators
    for i, (s, e) in enumerate(_LAYOUT['osc']):
        osc_pp: dict[str, Any] = {
            'kParamOctave': round(_denorm(vec[s + 0], 'octave')),
            'kParamVolume': float(_denorm(vec[s + 1], 'volume')),
            'kParamUnison': float(round(_denorm(vec[s + 2], 'unison'))),
            'kParamDetune': float(_denorm(vec[s + 3], 'detune')),
        }
        if vec[s + 4] > 0.5:
            osc_pp['kParamEnable'] = 1.0
        warp_block = vec[s + 5: s + 5 + len(WARP_MENUS) + 1]
        widx = int(np.argmax(warp_block))
        if warp_block[widx] > 0.5 and widx < len(WARP_MENUS):
            osc_pp[f'_WTOsc{i}_kParamWarpMenu'] = WARP_MENUS[widx]
        params[f'Oscillator{i}'] = osc_pp

    # Voice filters
    for i, (s, e) in enumerate(_LAYOUT['filter']):
        vf_pp: dict[str, Any] = {
            'kParamFreq': float(_denorm(vec[s + 0], 'freq')),
            'kParamReso': float(_denorm(vec[s + 1], 'reso')),
            'kParamDrive': float(_denorm(vec[s + 2], 'drive')),
        }
        if vec[s + 3] > 0.5:
            vf_pp['kParamEnable'] = 1.0
        type_block = vec[s + 4: s + 4 + len(FILTER_TYPES) + 1]
        tidx = int(np.argmax(type_block))
        if type_block[tidx] > 0.5 and tidx < len(FILTER_TYPES):
            vf_pp['kParamType'] = FILTER_TYPES[tidx]
        params[f'VoiceFilter{i}'] = vf_pp

    # FX chain
    has_fx = False
    for slot, (s, e) in enumerate(_LAYOUT['fx']):
        type_block = vec[s: s + _FX_TYPES_COUNT + 1]
        tidx = int(np.argmax(type_block))
        # empty slot or 'other' type -> stop
        if tidx == _FX_TYPES_COUNT or type_block[tidx] <= 0.5:
            continue
        has_fx = True
        drive = float(_denorm(vec[s + _FX_TYPES_COUNT + 1], 'fx_drive'))
        wet = float(_denorm(vec[s + _FX_TYPES_COUNT + 2], 'fx_wet'))
        freq = float(_denorm(vec[s + _FX_TYPES_COUNT + 3], 'fx_freq'))
        mod_name = FX_MODULE_NAMES.get(tidx, f'FX_{tidx}')
        fx_pp: dict[str, Any] = {}
        if drive > 0:
            fx_pp['kParamDrive'] = drive
        if wet > 0:
            fx_pp['kParamWet'] = wet
        if freq > 0:
            fx_pp['kParamFreq'] = freq
        if fx_pp:
            fx_pp['kParamEnable'] = 1.0
        item = {'type': tidx, mod_name: {'plainParams': fx_pp}}
        if tidx not in (7, 13, 14, 15):  # EQ / splitters carry no mix
            item['kUIParamMixOrGain'] = wet
        fx_chain.append(item)

    return {'params': params, 'fx_chain': fx_chain if has_fx else None}


def describe() -> dict[str, Any]:
    """Return schema metadata for UI / documentation."""
    return {
        'vector_dim': VECTOR_DIM,
        'oscillators': {'count': NUM_OSC, 'per_osc': _PER_OSC, 'warp_menus': len(WARP_MENUS)},
        'filters': {'count': NUM_FILTERS, 'per_filter': _PER_FILTER, 'filter_types': len(FILTER_TYPES)},
        'fx': {'max_slots': MAX_FX, 'per_slot': _PER_FX, 'fx_types': _FX_TYPES_COUNT},
    }


__all__ = [
    'VECTOR_DIM', 'WARP_MENUS', 'FILTER_TYPES', 'NUM_OSC', 'NUM_FILTERS', 'MAX_FX',
    'to_feature_vector', 'from_feature_vector', 'describe',
]
