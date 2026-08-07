"""
preset_generator.py — rule-based Serum preset generator (M1.2).

Takes an archetype template from preset_archetypes, applies seed-controlled
weighted random variation within "sounds-good" ranges, produces:
  1. .SerumPreset bytes (via sp.build_preset)
  2. feature_vector (via feature_vector.to_feature_vector)
  3. metadata dict

Avoids mod-matrix (keys unknown — M2 work). Uses direct params + LFO-as-envelope.
All output is offline file — no DAW connectivity required.
"""
from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from neuroman.tools import feature_vector as fv
from neuroman.tools import preset_archetypes as pa
from neuroman.tools import serum_preset as sp

# ─── Variation ranges per param ──────────────────────────────────────────
# {param_key: (center, half_range)}. Generator picks uniformly in [center-hr, center+hr].
# These encode the "sounds-good" envelopes from bass-engineering.md decision trees.
_RANGES: dict[str, tuple[float, float]] = {
    'kParamOctave': (-1.0, 1.0),
    'kParamVolume': (0.75, 0.2),
    'kParamDetune': (0.4, 0.25),
    'kParamUnison': (7.0, 5.0),
    'kParamUnisonStereo': (0.5, 0.4),
    'kParamFreq': (0.2, 0.15),
    'kParamReso': (25.0, 20.0),
    'kParamDrive': (15.0, 15.0),
}


def _rng(seed: int | None) -> np.random.Generator:
    return np.random.default_rng(seed)


def _vary_value(rng: np.random.Generator, key: str, base: float, variation: float) -> float:
    """Apply scaled random variation to a parameter value."""
    if key in _RANGES:
        center, half = _RANGES[key]
        delta = (base - center)  # offset from archetype center
        noise = rng.uniform(-half, half) * variation
        val = center + delta * (1.0 - variation) + noise
    else:
        # Generic: ±10% of base value, scaled by variation
        val = base * (1.0 + (rng.uniform(-0.1, 0.1) * variation))
    return round(val, 6)


def _vary_params(
    rng: np.random.Generator,
    params: dict[str, dict[str, Any]],
    variation: float,
) -> dict[str, dict[str, Any]]:
    """Deep-copy params and apply variation to numeric values."""
    import copy
    varied = copy.deepcopy(params)
    for mod_name, mod_params in varied.items():
        if not isinstance(mod_params, dict):
            continue
        for key, val in list(mod_params.items()):
            if isinstance(val, (int, float)) and not key.startswith('_'):
                mod_params[key] = _vary_value(rng, key, float(val), variation)
    return varied


def _vary_fx(
    rng: np.random.Generator,
    fx_chain: list[dict] | None,
    variation: float,
) -> list[dict] | None:
    """Deep-copy fx_chain and vary numeric params within each FX item."""
    if fx_chain is None:
        return None
    import copy
    varied = copy.deepcopy(fx_chain)
    for item in varied:
        for key, val in item.items():
            if isinstance(val, dict) and 'plainParams' in val:
                pp = val['plainParams']
                for pk, pv in list(pp.items()):
                    if isinstance(pv, (int, float)):
                        pp[pk] = _vary_value(rng, pk, float(pv), variation)
        if 'kUIParamMixOrGain' in item and isinstance(item['kUIParamMixOrGain'], (int, float)):
            item['kUIParamMixOrGain'] = _vary_value(rng, 'kParamWet', float(item['kUIParamMixOrGain']), variation)
    return varied


# ─── Public generate API ────────────────────────────────────────────────


def generate(
    archetype: str,
    *,
    seed: int | None = None,
    variation: float = 0.5,
    output_path: str | None = None,
    author: str = 'NeuroMan',
) -> dict[str, Any]:
    """
    Generate a Serum preset from an archetype template.

    Args:
        archetype: archetype id (growl/reese/hybrid/tech/pad)
        seed: RNG seed for reproducibility. None = non-deterministic.
        variation: 0.0 = template unchanged, 1.0 = max random variation.
        output_path: if set, write .SerumPreset to this path.
        author: preset author tag.

    Returns:
        dict with keys:
            preset_bytes: bytes of the .SerumPreset file
            feature_vector: list[float] (serializable)
            meta: {name, archetype, seed, variation, author, tags}
    """
    template = pa.get_archetype(archetype)

    # variation=0: deterministic regardless of seed
    if variation == 0.0:
        effective_seed = 0
    elif seed is not None:
        effective_seed = seed
    else:
        effective_seed = np.random.default_rng().integers(0, 2**63)

    rng = _rng(effective_seed)

    # Apply variation
    varied_params = _vary_params(rng, template.get('params', {}), variation)
    varied_fx = _vary_fx(rng, template.get('fx_chain'), variation)

    # Build preset name
    idx = rng.integers(1000, 9999)
    name = f"{template['name']} #{idx}"

    # Tags
    tags = ['Neurofunk', 'Generated', archetype.capitalize()]
    if archetype in ('growl', 'reese', 'hybrid', 'tech'):
        tags.append('Bass')
    elif archetype == 'pad':
        tags.append('Pad')

    # Build preset via serum_preset toolkit
    preset_bytes = sp.build_preset(
        name=name,
        author=author,
        tags=tags,
        params=varied_params,
        fx_chain=varied_fx,
        output_path=output_path,
    )

    # Compute feature vector from the generated cbor_dict
    # Re-decode to get exact feature vector (ensures round-trip consistency)
    _, cb = sp.decode_preset(preset_bytes)
    feature_vec = fv.to_feature_vector(cb)

    return {
        'preset_bytes': preset_bytes,
        'feature_vector': feature_vec.tolist(),
        'meta': {
            'name': name,
            'archetype': archetype,
            'seed': int(effective_seed),
            'variation': variation,
            'author': author,
            'tags': tags,
        },
    }


__all__ = ['generate', 'main']


def main():
    """CLI entry point. --stdio mode reads JSON from stdin, writes JSON to stdout."""
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(description='NeuroMan Serum preset generator')
    ap.add_argument('--stdio', action='store_true', help='Read JSON request from stdin, write JSON response to stdout')
    ap.add_argument('--archetype', type=str, help='Archetype name (growl/reese/hybrid/tech/pad)')
    ap.add_argument('--seed', type=int, default=None)
    ap.add_argument('--variation', type=float, default=0.5)
    ap.add_argument('--output', type=str, help='Output .SerumPreset file path')
    ap.add_argument('--list', action='store_true', help='List available archetypes')
    args = ap.parse_args()

    if args.list:
        for m in pa.archetype_metadata():
            print(f"  {m['id']:10s}  {m['name']:20s}  {m['description']}")
        return

    if args.stdio:
        line = sys.stdin.readline().strip()
        if not line:
            json.dump({'ok': False, 'error': 'No input received'}, sys.stdout)
            print()
            sys.exit(1)
        req = json.loads(line)
        archetype = req.get('archetype', 'growl')
        seed = req.get('seed', None)
        variation = float(req.get('variation', 0.5))
        output_path = req.get('output_path')
        try:
            result = generate(archetype, seed=seed, variation=variation, output_path=output_path)
            resp = {
                'ok': True,
                'preset_bytes_size': len(result['preset_bytes']),
                'preset_bytes_base64': __import__('base64').b64encode(result['preset_bytes']).decode('ascii'),
                'feature_vector': result['feature_vector'],
                'meta': result['meta'],
            }
            json.dump(resp, sys.stdout)
            print()
        except Exception as e:
            json.dump({'ok': False, 'error': str(e)}, sys.stdout)
            print()
        return

    # Direct CLI mode (non-stdio)
    if not args.archetype:
        ap.print_help()
        return
    try:
        result = generate(args.archetype, seed=args.seed, variation=args.variation, output_path=args.output)
        print(f"Generated: {result['meta']['name']} (seed={result['meta']['seed']})")
        if args.output:
            print(f"Written to: {args.output}")
        else:
            print(f"Preset bytes: {len(result['preset_bytes'])} bytes")
        print(f"Feature vector: {fv.VECTOR_DIM} dims")
    except (KeyError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
