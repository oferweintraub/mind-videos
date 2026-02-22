#!/usr/bin/env python3
"""
Clone voices for puppet characters using ElevenLabs Instant Voice Cloning.

Uses 3 audio clips (~90s each) per character from YouTube speeches/interviews.
Creates named voices in the ElevenLabs account for later TTS use.

Characters:
- Bibi (Netanyahu) - Hebrew speaker
- Trump - English speaker (will speak Hebrew with American accent)
- Kisch (Yoav Kisch) - Hebrew speaker
- Silman (Idit Silman) - Hebrew speaker
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

import requests

API_KEY = os.getenv("ELEVENLABS_API_KEY")
BASE_URL = "https://api.elevenlabs.io/v1"
CLONE_DIR = Path("output/voice_cloning")

CHARACTERS = {
    "bibi": {
        "name": "Puppet Bibi (Netanyahu)",
        "description": "Benjamin Netanyahu puppet voice clone from Hebrew speeches",
        "labels": {"language": "Hebrew", "character": "bibi", "type": "puppet_satire"},
    },
    "trump": {
        "name": "Puppet Trump",
        "description": "Donald Trump puppet voice clone from English rally speeches",
        "labels": {"language": "English", "character": "trump", "type": "puppet_satire"},
    },
    "kisch": {
        "name": "Puppet Kisch (Yoav Kisch)",
        "description": "Yoav Kisch puppet voice clone from Hebrew interviews",
        "labels": {"language": "Hebrew", "character": "kisch", "type": "puppet_satire"},
    },
    "silman": {
        "name": "Puppet Silman (Idit Silman)",
        "description": "Idit Silman puppet voice clone from Hebrew debates",
        "labels": {"language": "Hebrew", "character": "silman", "type": "puppet_satire"},
    },
}


def list_existing_voices():
    """Get existing voices to avoid duplicates."""
    resp = requests.get(
        f"{BASE_URL}/voices",
        headers={"xi-api-key": API_KEY},
    )
    resp.raise_for_status()
    voices = resp.json().get("voices", [])
    return {v["name"]: v["voice_id"] for v in voices}


def clone_voice(char_key: str, char_info: dict, existing: dict) -> str | None:
    """Clone a voice using IVC (Instant Voice Cloning)."""
    name = char_info["name"]

    if name in existing:
        print(f"  {char_key}: already exists (voice_id={existing[name]})")
        return existing[name]

    clip_dir = CLONE_DIR / char_key
    clips = sorted(clip_dir.glob("clip*.mp3"))
    if not clips:
        print(f"  {char_key}: no clips found in {clip_dir}")
        return None

    print(f"  {char_key}: cloning with {len(clips)} clips...")

    # Build multipart form data
    files = []
    for clip in clips:
        files.append(("files", (clip.name, open(clip, "rb"), "audio/mpeg")))

    data = {
        "name": name,
        "description": char_info["description"],
    }
    # Add labels as individual form fields
    for k, v in char_info["labels"].items():
        data[f"labels[{k}]"] = v

    resp = requests.post(
        f"{BASE_URL}/voices/add",
        headers={"xi-api-key": API_KEY},
        data=data,
        files=files,
    )

    # Close file handles
    for _, (_, fh, _) in files:
        fh.close()

    if resp.status_code != 200:
        print(f"  {char_key}: FAILED ({resp.status_code}) - {resp.text[:200]}")
        return None

    voice_id = resp.json().get("voice_id")
    print(f"  {char_key}: SUCCESS (voice_id={voice_id})")
    return voice_id


def main():
    if not API_KEY:
        print("ERROR: ELEVENLABS_API_KEY not set")
        sys.exit(1)

    print("=" * 60)
    print("VOICE CLONING — ElevenLabs IVC")
    print("=" * 60)

    # Check existing voices
    existing = list_existing_voices()
    print(f"\nExisting voices: {len(existing)}")

    # Clone each character
    results = {}
    for char_key, char_info in CHARACTERS.items():
        voice_id = clone_voice(char_key, char_info, existing)
        if voice_id:
            results[char_key] = voice_id

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for char_key, voice_id in results.items():
        print(f"  {char_key}: {voice_id}")

    # Save voice IDs to file for later use
    ids_file = CLONE_DIR / "voice_ids.txt"
    with open(ids_file, "w") as f:
        for char_key, voice_id in results.items():
            f.write(f"{char_key}={voice_id}\n")
    print(f"\nVoice IDs saved to {ids_file}")


if __name__ == "__main__":
    main()
