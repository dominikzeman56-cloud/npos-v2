import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
pytest.importorskip("numpy")
pytest.importorskip("scipy")
import analyze_track as at  # noqa: E402


@pytest.mark.parametrize("rate,bpm,label", [
    (2.9, 174, "1/4"),     # one per beat
    (5.8, 174, "1/8"),     # was reported as off_grid before the fix (First Contact, Breach, Sequence)
    (5.74, 172.3, "1/8"),
    (11.6, 174, "1/16"),
    (23.2, 174, "1/32"),
    (3.62, 172.3, "off_grid"),
])
def test_grid_label(rate, bpm, label):
    assert at.grid_label(rate, bpm) == label


def test_crest_ignores_quiet_parts():
    import numpy as np
    sr = at.SR
    rng = np.random.default_rng(0)
    loud = np.clip(rng.normal(0, 0.5, 12 * sr), -1, 1)          # dense "drop"
    quiet = rng.normal(0, 0.02, 30 * sr)                           # breakdown in the same window
    whole = np.concatenate([quiet, loud, quiet])
    naive = 20 * np.log10(np.abs(whole).max() / np.sqrt(np.mean(whole ** 2)))
    c = at.loudest_window_crest(whole)
    assert abs(c - at.loudest_window_crest(loud)) < 0.5 and naive - c > 3
