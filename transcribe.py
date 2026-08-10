#!/usr/bin/env python3
"""
transcribe.py — Transcribe workshop videos using faster-whisper.

Usage:
  python transcribe.py video.mp4                       # auto-detect language
  python transcribe.py video.mp4 --lang es             # force Spanish
  python transcribe.py video.mp4 --model large-v3      # most accurate (default)
  python transcribe.py video.mp4 --model medium        # faster, good accuracy
  python transcribe.py video.mp4 --output srt          # export SRT subtitles
  python transcribe.py video.mp4 --output txt          # plain text only
  python transcribe.py youtube_url                     # download + transcribe
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def check_deps():
    """Check ffmpeg is available."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Error: ffmpeg not found. Install with: winget install ffmpeg")
        sys.exit(1)


def extract_audio(video_path: str, out_wav: str):
    """Extract audio as 16kHz mono WAV for whisper."""
    print(f"  Extracting audio from {video_path}...")
    subprocess.run(
        ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
         "-ar", "16000", "-ac", "1", "-y", out_wav],
        capture_output=True, check=True
    )


def download_youtube_audio(url: str, out_dir: str) -> str:
    """Download audio from YouTube using yt-dlp."""
    print(f"  Downloading audio from {url}...")
    result = subprocess.run(
        ["yt-dlp", "-x", "--audio-format", "wav", "--audio-quality", "0",
         "-o", f"{out_dir}/%(id)s.%(ext)s", url],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  yt-dlp failed: {result.stderr}")
        sys.exit(1)
    # Find the downloaded file
    for f in os.listdir(out_dir):
        if f.endswith(".wav"):
            return os.path.join(out_dir, f)
    print("  Error: No audio file downloaded")
    sys.exit(1)


def transcribe(audio_path: str, model_name: str, lang: str = None,
               output_dir: str = None, output_format: str = "srt",
               original_name: str = None):
    """Run faster-whisper transcription."""
    from faster_whisper import WhisperModel

    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    os.makedirs(model_path, exist_ok=True)

    print(f"  Loading model '{model_name}'...")
    # Use int8 for CPU — much faster, minimal accuracy loss
    model = WhisperModel(model_name, device="cpu", compute_type="int8",
                         download_root=model_path)

    print(f"  Transcribing {audio_path}...")
    start = time.time()

    opts = {}
    if lang:
        opts["language"] = lang

    segments, info = model.transcribe(audio_path, beam_size=5, **opts)
    detected_lang = info.language
    duration = info.duration

    segments_list = list(segments)
    elapsed = time.time() - start
    audio_min = duration / 60
    realtime = elapsed / duration if duration > 0 else 0

    print(f"  Done: {len(segments_list)} segments | "
          f"lang={detected_lang} | "
          f"{audio_min:.1f}min audio in {elapsed:.0f}s "
          f"({realtime:.2f}x realtime)")

    base_name = original_name or os.path.splitext(os.path.basename(audio_path))[0]
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        base = os.path.join(output_dir, base_name)
    else:
        base = os.path.splitext(audio_path)[0]

    if output_format in ("txt", "all"):
        txt_path = base + ".txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            for seg in segments_list:
                f.write(seg.text.strip() + "\n")
        print(f"  TXT: {txt_path}")

    if output_format in ("srt", "all"):
        srt_path = base + ".srt"
        _write_srt(segments_list, srt_path)
        print(f"  SRT: {srt_path}")

    if output_format in ("json", "all"):
        json_path = base + ".json"
        _write_json(segments_list, detected_lang, json_path)
        print(f"  JSON: {json_path}")

    return detected_lang


def _write_srt(segments, path: str):
    """Write SRT subtitle file."""
    def _ts(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{_ts(seg.start)} --> {_ts(seg.end)}\n")
            f.write(seg.text.strip() + "\n\n")


def _write_json(segments, lang, path: str):
    """Write JSON with timestamps."""
    data = {
        "language": lang,
        "segments": [
            {"start": round(s.start, 2), "end": round(s.end, 2),
             "text": s.text.strip()}
            for s in segments
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe workshop videos with faster-whisper")
    parser.add_argument("input", help="Video file path or YouTube URL")
    parser.add_argument("--lang", "-l", default=None,
                        help="Language code (es, en, pt, auto-detect if omitted)")
    parser.add_argument("--model", "-m", default="large-v3",
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help="Whisper model size (default: large-v3)")
    parser.add_argument("--output", "-o", default="srt",
                        choices=["txt", "srt", "json", "all"],
                        help="Output format (default: srt)")
    parser.add_argument("--dir", "-d", default=None,
                        help="Output directory (default: same as input)")
    parser.add_argument("--keep-audio", action="store_true",
                        help="Keep extracted WAV file (default: delete)")

    args = parser.parse_args()
    check_deps()

    input_path = args.input
    is_url = input_path.startswith(("http://", "https://", "youtube.com", "youtu.be"))
    tmp_dir = None
    original_name = None

    try:
        if is_url:
            # Check yt-dlp
            if not subprocess.run(["yt-dlp", "--version"],
                                  capture_output=True).returncode == 0:
                print("Install yt-dlp: pip install yt-dlp")
                sys.exit(1)

            tmp_dir = tempfile.mkdtemp(prefix="transcribe_")
            audio_path = download_youtube_audio(input_path, tmp_dir)
        else:
            if not os.path.isfile(input_path):
                print(f"Error: file not found: {input_path}")
                sys.exit(1)

            original_name = os.path.splitext(os.path.basename(input_path))[0]
            ext = os.path.splitext(input_path)[1].lower()
            if ext == ".wav":
                audio_path = input_path
            else:
                tmp_dir = tempfile.mkdtemp(prefix="transcribe_")
                audio_path = os.path.join(tmp_dir, "audio.wav")
                extract_audio(input_path, audio_path)

        detected = transcribe(audio_path, args.model, args.lang,
                              args.dir, args.output, original_name)

        print(f"  Detected language: {detected}")

    finally:
        # Cleanup temp audio
        if tmp_dir and not args.keep_audio:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()