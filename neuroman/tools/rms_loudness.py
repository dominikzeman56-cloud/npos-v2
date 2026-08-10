# neuroman/tools/rms_loudness.py
"""RMS loudness utilities for PCM WAV files (stdlib only)."""

from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Union

PathLike = Union[str, Path]


@dataclass(frozen=True, slots=True)
class RmsResult:
    """RMS measurement for a WAV file."""

    path: str
    sample_rate: int
    channels: int
    sample_width: int  # bytes per sample (1, 2, 3, or 4)
    num_frames: int
    duration_sec: float
    rms_linear: float  # 0.0 .. 1.0 (full-scale normalized)
    rms_dbfs: float  # dBFS; -inf if silence
    peak_linear: float  # 0.0 .. 1.0
    peak_dbfs: float

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "sample_width": self.sample_width,
            "num_frames": self.num_frames,
            "duration_sec": self.duration_sec,
            "rms_linear": self.rms_linear,
            "rms_dbfs": self.rms_dbfs,
            "peak_linear": self.peak_linear,
            "peak_dbfs": self.peak_dbfs,
        }


def _linear_to_dbfs(level: float) -> float:
    if level <= 0.0:
        return float("-inf")
    return 20.0 * math.log10(level)


def _full_scale(sample_width: int) -> float:
    """Positive full-scale magnitude for signed PCM of given width."""
    bits = sample_width * 8
    # signed range is -(2^(bits-1)) .. 2^(bits-1)-1
    return float(1 << (bits - 1))


def _unpack_frames(raw: bytes, sample_width: int, n_samples: int) -> list[float]:
    """Decode interleaved PCM samples to normalized floats in [-1.0, 1.0]."""
    if n_samples == 0:
        return []

    if sample_width == 1:
        # 8-bit WAV is unsigned [0, 255], midpoint 128
        vals = struct.unpack(f"<{n_samples}B", raw)
        return [(v - 128) / 128.0 for v in vals]

    if sample_width == 2:
        vals = struct.unpack(f"<{n_samples}h", raw)
        scale = _full_scale(2)
        return [v / scale for v in vals]

    if sample_width == 4:
        vals = struct.unpack(f"<{n_samples}i", raw)
        scale = _full_scale(4)
        return [v / scale for v in vals]

    if sample_width == 3:
        # 24-bit little-endian packed; sign-extend to 32-bit int
        out: list[float] = []
        scale = _full_scale(3)
        for i in range(0, len(raw), 3):
            b0, b1, b2 = raw[i], raw[i + 1], raw[i + 2]
            val = b0 | (b1 << 8) | (b2 << 16)
            if val & 0x800000:
                val |= ~0xFFFFFF  # sign extend
            out.append(val / scale)
        return out

    raise ValueError(f"Unsupported sample width: {sample_width} bytes")


def calculate_rms_loudness(
    wav_path: PathLike,
    *,
    chunk_frames: int = 65_536,
) -> RmsResult:
    """
    Compute RMS and peak loudness of a PCM WAV file.

    Parameters
    ----------
    wav_path:
        Path to a .wav file (PCM integer formats: 8/16/24/32-bit).
    chunk_frames:
        Frames per read chunk (memory-friendly streaming).

    Returns
    -------
    RmsResult
        Linear (0..1 FS) and dBFS RMS/peak plus basic file metadata.

    Raises
    ------
    FileNotFoundError
        If path does not exist.
    wave.Error / ValueError
        If file is not a readable PCM WAV.
    """
    path = Path(wav_path)
    if not path.is_file():
        raise FileNotFoundError(f"WAV not found: {path}")

    with wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        comptype = wf.getcomptype()

        if comptype not in ("NONE", "not compressed"):
            raise ValueError(f"Compressed WAV not supported (comptype={comptype!r})")
        if sample_width not in (1, 2, 3, 4):
            raise ValueError(f"Unsupported sampwidth={sample_width}")
        if n_channels < 1:
            raise ValueError("WAV has zero channels")

        sum_sq = 0.0
        peak = 0.0
        total_samples = 0
        remaining = n_frames

        while remaining > 0:
            take = min(chunk_frames, remaining)
            raw = wf.readframes(take)
            if not raw:
                break
            n_samp = (len(raw) // sample_width)
            samples = _unpack_frames(raw, sample_width, n_samp)
            for s in samples:
                a = abs(s)
                if a > peak:
                    peak = a
                sum_sq += s * s
            total_samples += len(samples)
            remaining -= take

    if total_samples == 0:
        rms = 0.0
    else:
        rms = math.sqrt(sum_sq / total_samples)

    duration = n_frames / float(sample_rate) if sample_rate else 0.0

    return RmsResult(
        path=str(path.resolve()),
        sample_rate=sample_rate,
        channels=n_channels,
        sample_width=sample_width,
        num_frames=n_frames,
        duration_sec=duration,
        rms_linear=rms,
        rms_dbfs=_linear_to_dbfs(rms),
        peak_linear=peak,
        peak_dbfs=_linear_to_dbfs(peak),
    )


def calculate_rms_dbfs(wav_path: PathLike) -> float:
    """Convenience: return only RMS level in dBFS."""
    return calculate_rms_loudness(wav_path).rms_dbfs


if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Compute RMS loudness of a WAV file.")
    parser.add_argument("wav", type=Path, help="Path to PCM WAV")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    try:
        result = calculate_rms_loudness(args.wav)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(f"file:     {result.path}")
        print(f"format:   {result.sample_rate} Hz, {result.channels} ch, {result.sample_width * 8}-bit")
        print(f"duration: {result.duration_sec:.3f} s ({result.num_frames} frames)")
        print(f"RMS:      {result.rms_linear:.6f} FS  ({result.rms_dbfs:.2f} dBFS)")
        print(f"peak:     {result.peak_linear:.6f} FS  ({result.peak_dbfs:.2f} dBFS)")
