"""
preset_archetypes.py — neurofunk bass archetypes for the rule-based generator (M1.2).

Each archetype encodes the design recipe from references/bass-engineering.md as a
deterministic template {params, fx_chain}. The generator applies weighted random
variation on top of these templates (see preset_generator.py).

Archetypes map 1:1 to the bass-engineering.md table:
  growl   - synced LFO, FM, filter movement, wavetable motion
  reese   - detune, beating, phasing, distortion, filtering
  hybrid  - reese body + growl articulation
  tech    - FM, comb, band reject, tight automation
  pad     - long env, chorus+reverb, low resonance (bonus non-bass texture)

All templates reuse sp.build_preset() conventions: params overlay modules on the
default.SerumPreset template; fx_chain replaces FXRack0. Warp sub-modules are
inherited from the template (cannot be built from scratch — see serum_preset.py).
"""
from __future__ import annotations

from typing import Any

from neuroman.tools.serum_preset import make_fx_item

# ─── Oscillator helpers ─────────────────────────────────────────────────


def _osc(octave: float, volume: float, unison: float, detune: float, enable: float = 1.0) -> dict[str, Any]:
    return {
        'kParamOctave': float(octave),
        'kParamVolume': float(volume),
        'kParamUnison': float(unison),
        'kParamDetune': float(detune),
        'kParamEnable': float(enable),
        'kParamUnisonStereo': 0.5,
    }


def _filter(ftype: str, freq: float, reso: float, drive: float, enable: float = 1.0) -> dict[str, Any]:
    return {
        'kParamType': ftype,
        'kParamFreq': float(freq),
        'kParamReso': float(reso),
        'kParamDrive': float(drive),
        'kParamEnable': float(enable),
    }


# ─── Archetype definitions ──────────────────────────────────────────────

_ARCHETYPES: dict[str, dict[str, Any]] = {
    # ─── Growl ── synced LFO + filter movement + controlled distortion ──
    'growl': {
        'name': 'Growl Bass',
        'description': 'Speech-like aggression. Synced LFO, filter movement, controlled distortion before/after filter.',
        'params': {
            'Oscillator0': _osc(octave=-1, volume=0.8, unison=7, detune=0.35),
            'Oscillator1': _osc(octave=-1, volume=0.8, unison=7, detune=0.35),
            'Oscillator2': _osc(octave=-2, volume=0.7, unison=1, detune=0.0),  # sub
            'VoiceFilter0': _filter('MgL24', freq=0.12, reso=35.0, drive=20.0),
            'VoiceFilter1': _filter('BandReject', freq=0.3, reso=15.0, drive=10.0, enable=0.0),
        },
        'fx_chain': [
            make_fx_item(0, mix=40.0, params={  # Distortion - controlled bite
                'kParamMode': 'kSoftClip', 'kParamNumStages': 2.0, 'kParamDrive': 45.0,
                'kParamWet': 60.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(8, mix=70.0, params={  # Filter - extra movement
                'kParamType': 'MgL24', 'kParamFreq': 0.25, 'kParamReso': 25.0,
                'kParamDrive': 5.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(7, params={  # EQ - shape
                'kParamFreq1': 250.0, 'kParamGain1': -2.0, 'kParamReso1': 48.0,
                'kParamFreq2': 3500.0, 'kParamGain2': 3.0, 'kParamReso2': 48.0,
                'kParamEnable': 1.0,
            }),
            make_fx_item(5, mix=70.0, params={  # Compressor OTT
                'kParamMultiband': 1.0, 'kParamAttack': 5.0, 'kParamRelease': 80.0,
                'kParamRatio': 4.0, 'kParamThresh': 0.3, 'kParamMakeup': 3.0,
                'kParamWet': 70.0, 'kParamEnable': 1.0,
            }),
        ],
    },

    # ─── Reese ── high detune + unison, beating/phasing, distortion after filter ──
    'reese': {
        'name': 'Reese Bass',
        'description': 'Sustained pressure and width. High detune, beating/phasing, distortion after filter.',
        'params': {
            'Oscillator0': _osc(octave=-1, volume=0.8, unison=11, detune=0.55),
            'Oscillator1': _osc(octave=-1, volume=0.8, unison=11, detune=0.55),
            'Oscillator2': _osc(octave=-2, volume=0.6, unison=1, detune=0.0),
            'VoiceFilter0': _filter('MgL18', freq=0.15, reso=20.0, drive=8.0),
            'VoiceFilter1': _filter('FlangeP', freq=0.4, reso=10.0, drive=0.0, enable=0.0),
        },
        'fx_chain': [
            make_fx_item(8, mix=60.0, params={  # Filter - low pass body
                'kParamType': 'MgL18', 'kParamFreq': 0.2, 'kParamReso': 15.0,
                'kParamDrive': 5.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(0, mix=50.0, params={  # Distortion AFTER filter (reese rule)
                'kParamMode': 'kDiode1', 'kParamDrive': 35.0,
                'kParamWet': 50.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(2, mix=30.0, params={  # Phaser - width/movement
                'kParamRate': 0.3, 'kParamDepth': 40.0, 'kParamFeedback': 20.0,
                'kParamWet': 30.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(7, params={
                'kParamFreq1': 200.0, 'kParamGain1': -3.0, 'kParamReso1': 48.0,
                'kParamFreq2': 2000.0, 'kParamGain2': 1.0, 'kParamReso2': 48.0,
                'kParamEnable': 1.0,
            }),
        ],
    },

    # ─── Hybrid ── reese body + growl articulation ──
    'hybrid': {
        'name': 'Hybrid Bass',
        'description': 'Modern neuro movement with weight. Reese body + growl articulation layer.',
        'params': {
            'Oscillator0': _osc(octave=-1, volume=0.75, unison=9, detune=0.45),
            'Oscillator1': _osc(octave=-1, volume=0.75, unison=9, detune=0.45),
            'Oscillator2': _osc(octave=-2, volume=0.7, unison=1, detune=0.0),
            'VoiceFilter0': _filter('MgL24', freq=0.14, reso=28.0, drive=15.0),
            'VoiceFilter1': _filter('LH12', freq=0.3, reso=18.0, drive=8.0, enable=0.0),
        },
        'fx_chain': [
            make_fx_item(0, mix=35.0, params={
                'kParamMode': 'kOverdrive', 'kParamDrive': 40.0,
                'kParamWet': 55.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(8, mix=65.0, params={
                'kParamType': 'MgL24', 'kParamFreq': 0.22, 'kParamReso': 22.0,
                'kParamDrive': 8.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(9, mix=20.0, params={  # Hyper/Dimension - width
                'kParamDimEWet': 15.0, 'kParamDimESize': 10.0,
                'kParamWet': 20.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(7, params={
                'kParamFreq1': 300.0, 'kParamGain1': -2.0, 'kParamReso1': 48.0,
                'kParamFreq2': 5000.0, 'kParamGain2': 2.0, 'kParamReso2': 48.0,
                'kParamEnable': 1.0,
            }),
            make_fx_item(5, mix=60.0, params={
                'kParamMultiband': 1.0, 'kParamAttack': 8.0, 'kParamRelease': 100.0,
                'kParamRatio': 3.0, 'kParamThresh': 0.35, 'kParamMakeup': 2.5,
                'kParamWet': 60.0, 'kParamEnable': 1.0,
            }),
        ],
    },

    # ─── Tech / FM ── FM, comb, band reject, tight automation ──
    'tech': {
        'name': 'Tech FM Bass',
        'description': 'Precise, metallic, aggressive phrases. FM, comb/band-reject, tight filter automation.',
        'params': {
            'Oscillator0': _osc(octave=0, volume=0.75, unison=5, detune=0.2),
            'Oscillator1': _osc(octave=0, volume=0.75, unison=5, detune=0.2),
            'Oscillator2': _osc(octave=-2, volume=0.65, unison=1, detune=0.0),
            'VoiceFilter0': _filter('CombP', freq=0.35, reso=30.0, drive=12.0),
            'VoiceFilter1': _filter('BandReject', freq=0.45, reso=25.0, drive=10.0, enable=0.0),
        },
        'fx_chain': [
            make_fx_item(0, mix=45.0, params={
                'kParamMode': 'kHardClip', 'kParamDrive': 55.0,
                'kParamWet': 65.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(8, mix=70.0, params={
                'kParamType': 'BandReject', 'kParamFreq': 0.4, 'kParamReso': 28.0,
                'kParamDrive': 10.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(7, params={
                'kParamFreq1': 400.0, 'kParamGain1': -3.0, 'kParamReso1': 60.0,
                'kParamFreq2': 6000.0, 'kParamGain2': 4.0, 'kParamReso2': 60.0,
                'kParamEnable': 1.0,
            }),
            make_fx_item(5, mix=75.0, params={
                'kParamMultiband': 1.0, 'kParamAttack': 2.0, 'kParamRelease': 60.0,
                'kParamRatio': 4.0, 'kParamThresh': 0.25, 'kParamMakeup': 3.5,
                'kParamWet': 75.0, 'kParamEnable': 1.0,
            }),
        ],
    },

    # ─── Pad ── long env, chorus+reverb, low resonance (texture) ──
    'pad': {
        'name': 'Neuro Pad',
        'description': 'Atmospheric texture. Long envelopes, chorus + reverb, low resonance.',
        'params': {
            'Oscillator0': _osc(octave=0, volume=0.6, unison=9, detune=0.4),
            'Oscillator1': _osc(octave=1, volume=0.6, unison=9, detune=0.4),
            'Oscillator2': _osc(octave=-1, volume=0.5, unison=1, detune=0.0),
            'VoiceFilter0': _filter('MgL12', freq=0.4, reso=8.0, drive=3.0),
            'VoiceFilter1': _filter('LadderEMS', freq=0.5, reso=6.0, drive=2.0, enable=0.0),
        },
        'fx_chain': [
            make_fx_item(3, mix=40.0, params={  # Chorus - movement/width
                'kParamRate': 0.4, 'kParamDepth': 35.0, 'kParamFeedback': 15.0,
                'kParamFiltMode': 1.0, 'kParamFilt': 8000.0,
                'kParamWet': 40.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(9, mix=30.0, params={  # Hyper/Dimension
                'kParamDimEWet': 30.0, 'kParamDimESize': 25.0,
                'kParamWet': 30.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(6, mix=45.0, params={  # Reverb
                'kParamType': 'kHall', 'kParamSize': 60.0, 'kParamFeedback': 40.0,
                'kParamWidth': 80.0, 'kParamWet': 45.0, 'kParamEnable': 1.0,
            }),
            make_fx_item(7, params={
                'kParamFreq1': 150.0, 'kParamGain1': -2.0, 'kParamReso1': 40.0,
                'kParamFreq2': 8000.0, 'kParamGain2': 2.0, 'kParamReso2': 40.0,
                'kParamEnable': 1.0,
            }),
        ],
    },
}


# ─── Public registry API ────────────────────────────────────────────────


def list_archetypes() -> list[str]:
    """Return archetype ids in canonical order."""
    return ['growl', 'reese', 'hybrid', 'tech', 'pad']


def get_archetype(archetype_id: str) -> dict[str, Any]:
    """Return the template dict for an archetype. Raises KeyError if unknown."""
    if archetype_id not in _ARCHETYPES:
        raise KeyError(f'Unknown archetype: {archetype_id}. Known: {list(_ARCHETYPES)}')
    return _ARCHETYPES[archetype_id]


def archetype_metadata() -> list[dict[str, str]]:
    """Return [{id, name, description}] for UI listing."""
    return [
        {'id': aid, 'name': _ARCHETYPES[aid]['name'], 'description': _ARCHETYPES[aid]['description']}
        for aid in list_archetypes()
    ]


__all__ = ['list_archetypes', 'get_archetype', 'archetype_metadata']
