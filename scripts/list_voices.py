"""Print the voice catalog.

Usage:
    python scripts/list_voices.py
    python scripts/list_voices.py --good-for old_man   # filter
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "config" / "voices.yaml"


def main():
    p = argparse.ArgumentParser(description="List the ElevenLabs voice catalog")
    p.add_argument("--good-for", help="Filter to voices tagged with this good_for value")
    args = p.parse_args()

    if not CATALOG.exists():
        sys.exit(f"ERROR: voice catalog not found at {CATALOG}")
    data = yaml.safe_load(CATALOG.read_text())
    voices = data.get("voices", [])
    if args.good_for:
        voices = [v for v in voices if args.good_for in v.get("good_for", [])]

    if not voices:
        print("(no voices match)")
        return

    name_w = max(len(v["name"]) for v in voices)
    tone_w = max(len(v["tone"]) for v in voices)
    print(f"{'ID':<24}  {'NAME':<{name_w}}  {'TONE':<{tone_w}}  GOOD_FOR")
    print(f"{'-'*24}  {'-'*name_w}  {'-'*tone_w}  --------")
    for v in voices:
        print(f"{v['id']:<24}  {v['name']:<{name_w}}  {v['tone']:<{tone_w}}  "
              f"{', '.join(v['good_for'])}")

    print(f"\nDefaults: {data.get('defaults', {})}")
    print("To browse more voices: https://elevenlabs.io/voice-library")


if __name__ == "__main__":
    main()
