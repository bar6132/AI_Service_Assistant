"""Optional: render the guide's narration with a LOCAL neural voice (Piper).

The page already reads aloud with your browser's built-in voices. Run this once
if you want a more natural, fully offline voice. The page then plays the files
in guide/audio/<chapter>/<n>.wav and falls back to the browser voice for any
paragraph that has no file.

  pip install piper-tts
  # download a voice (an .onnx and its .onnx.json) from
  # https://huggingface.co/rhasspy/piper-voices  e.g. en_US-lessac-medium
  python guide/tools/make_audio.py --voice path/to/en_US-lessac-medium.onnx
  python guide/build.py          # tells the page which chapters have audio

NOTE: written against Piper's Python API but not run in the session that
created it (no voice was downloaded). If a Piper release changed the method
name, adjust synth() below.
"""

import argparse
import json
import wave
from pathlib import Path

GUIDE = Path(__file__).resolve().parents[1]


def narration(lesson):
    out = {}
    for b in lesson["blocks"]:
        if "n" in b:
            out[b["n"]] = b["say"]
        for it in b.get("items", []):
            out[it["n"]] = it["say"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True, help="path to a Piper .onnx voice")
    ap.add_argument("--only", help="render just this chapter id, e.g. 04-policy")
    ap.add_argument("--force", action="store_true", help="re-render files that already exist")
    args = ap.parse_args()

    from piper import PiperVoice  # imported late so --help works without it

    voice = PiperVoice.load(args.voice)

    def synth(text, path):
        with wave.open(str(path), "wb") as wf:
            if hasattr(voice, "synthesize_wav"):
                voice.synthesize_wav(text, wf)
            else:
                voice.synthesize(text, wf)

    lessons = json.loads((GUIDE / "data" / "lessons.json").read_text(encoding="utf-8"))
    for lesson in lessons:
        if args.only and lesson["id"] != args.only:
            continue
        folder = GUIDE / "audio" / lesson["id"]
        folder.mkdir(parents=True, exist_ok=True)
        lines = narration(lesson)
        for n, text in sorted(lines.items()):
            target = folder / f"{n}.wav"
            if target.exists() and not args.force:
                continue
            if text.strip():
                synth(text, target)
        print(f"{lesson['id']}: {len(lines)} clips")


if __name__ == "__main__":
    main()
