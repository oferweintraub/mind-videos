#!/usr/bin/env python3
"""
Quick test: Resemble AI API + ChatterBox (fal.ai) for Hebrew speech-to-speech.

Uses existing voice cloning clips as source audio to test conversion.
"""

import asyncio
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

OUTPUT_DIR = Path("output/s2s_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Source audio: use Bibi clip as the "recording" to convert
SOURCE_AUDIO = Path("output/voice_cloning/bibi/clip2.mp3")
# Target voice reference: Kisch (convert Bibi's voice → Kisch's voice)
TARGET_REF = Path("output/voice_cloning/kisch/clip2.mp3")


# ============================================================================
# TEST 1: Resemble AI API
# ============================================================================

async def test_resemble_api():
    """Test Resemble AI API — list voices and attempt S2S conversion."""
    print("\n" + "=" * 60)
    print("TEST 1: Resemble AI API")
    print("=" * 60)

    api_key = os.getenv("RESEMBLE_API_KEY")
    if not api_key:
        print("  ERROR: RESEMBLE_API_KEY not set in .env")
        return

    print(f"  API Key: {api_key[:8]}...")

    import requests

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Step 1: List voices
    print("\n  1. Listing voices...")
    try:
        resp = requests.get("https://app.resemble.ai/api/v2/voices", headers=headers, params={"page": 1, "page_size": 10})
        print(f"     Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            voices = data.get("items", data.get("voices", []))
            if not voices and isinstance(data, dict):
                # Try to find voices in different response formats
                print(f"     Response keys: {list(data.keys())}")
                print(f"     Full response: {str(data)[:500]}")
            else:
                for v in voices:
                    name = v.get("name", "?")
                    uuid = v.get("uuid", "?")
                    status = v.get("status", "?")
                    print(f"     - {name} (uuid={uuid}, status={status})")
        else:
            print(f"     Response: {resp.text[:500]}")
    except Exception as e:
        print(f"     ERROR: {e}")

    # Step 2: List projects
    print("\n  2. Listing projects...")
    try:
        resp = requests.get("https://app.resemble.ai/api/v2/projects", headers=headers, params={"page": 1, "page_size": 10})
        print(f"     Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            projects = data.get("items", data.get("projects", []))
            if not projects and isinstance(data, dict):
                print(f"     Response keys: {list(data.keys())}")
                print(f"     Full response: {str(data)[:500]}")
            else:
                for p in projects:
                    name = p.get("name", "?")
                    uuid = p.get("uuid", "?")
                    print(f"     - {name} (uuid={uuid})")
        else:
            print(f"     Response: {resp.text[:500]}")
    except Exception as e:
        print(f"     ERROR: {e}")

    # Step 3: Try the sync synthesis endpoint (to check API connectivity)
    print("\n  3. Testing synthesis endpoint...")
    try:
        # Simple TTS test first (not S2S)
        resp = requests.post(
            "https://f.cluster.resemble.ai/synthesize",
            headers=headers,
            json={
                "data": "<speak>שלום, זה בדיקה של המערכת</speak>",
                "output_format": "wav",
                "sample_rate": 22050,
                "precision": "PCM_16",
            },
            timeout=30,
        )
        print(f"     Status: {resp.status_code}")
        result = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text[:300]}
        if result.get("success"):
            audio_bytes = base64.b64decode(result["audio_content"])
            out_path = OUTPUT_DIR / "resemble_tts_test.wav"
            out_path.write_bytes(audio_bytes)
            print(f"     TTS test saved to {out_path} ({len(audio_bytes):,} bytes)")
        else:
            print(f"     Response: {str(result)[:500]}")
    except Exception as e:
        print(f"     ERROR: {e}")


# ============================================================================
# TEST 2: ChatterBox via fal.ai
# ============================================================================

async def test_chatterbox_fal():
    """Test ChatterBox speech-to-speech via fal.ai."""
    print("\n" + "=" * 60)
    print("TEST 2: ChatterBox Speech-to-Speech (fal.ai)")
    print("=" * 60)

    import fal_client
    import httpx

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if not api_key:
        print("  ERROR: FAL_KEY not set in .env")
        return

    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key
    print(f"  FAL Key: {api_key[:8]}...")

    if not SOURCE_AUDIO.exists():
        print(f"  ERROR: Source audio not found: {SOURCE_AUDIO}")
        return
    if not TARGET_REF.exists():
        print(f"  ERROR: Target reference not found: {TARGET_REF}")
        return

    # Upload source and target
    print(f"\n  Uploading source: {SOURCE_AUDIO.name} ({SOURCE_AUDIO.stat().st_size:,} bytes)")
    source_url = await fal_client.upload_async(SOURCE_AUDIO.read_bytes(), content_type="audio/mpeg")
    print(f"  Uploading target ref: {TARGET_REF.name} ({TARGET_REF.stat().st_size:,} bytes)")
    target_url = await fal_client.upload_async(TARGET_REF.read_bytes(), content_type="audio/mpeg")

    # Convert: Bibi's voice → Kisch's voice (keeping Bibi's intonation/speech)
    print(f"\n  Converting: Bibi clip → Kisch voice...")
    print(f"  (This preserves Bibi's Hebrew speech/intonation but changes to Kisch's voice)")

    try:
        result = await fal_client.run_async("fal-ai/chatterbox/speech-to-speech", arguments={
            "source_audio_url": source_url,
            "target_voice_audio_url": target_url,
        })

        print(f"  Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

        audio_out = result.get("audio", {}).get("url") if isinstance(result, dict) else None
        if audio_out:
            async with httpx.AsyncClient(timeout=120.0) as http:
                resp = await http.get(audio_out)
                out_path = OUTPUT_DIR / "chatterbox_s2s_test.wav"
                out_path.write_bytes(resp.content)
                print(f"  Saved to {out_path} ({len(resp.content):,} bytes)")
                print(f"  SUCCESS — listen to compare!")
        else:
            print(f"  Full result: {result}")

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# TEST 3: ChatterBox Multilingual TTS (text → speech, Hebrew)
# ============================================================================

async def test_chatterbox_tts():
    """Test ChatterBox Multilingual TTS for Hebrew via fal.ai."""
    print("\n" + "=" * 60)
    print("TEST 3: ChatterBox Multilingual TTS — Hebrew (fal.ai)")
    print("=" * 60)

    import fal_client
    import httpx

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if not api_key:
        print("  ERROR: FAL_KEY not set in .env")
        return

    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    # Upload a voice reference for cloning
    print(f"  Uploading voice ref: {TARGET_REF.name}")
    ref_url = await fal_client.upload_async(TARGET_REF.read_bytes(), content_type="audio/mpeg")

    hebrew_text = "שלום, אני רוצה לבדוק איך המערכת הזאת עובדת עם עברית. האם ההגייה נכונה?"

    print(f"  Text: {hebrew_text}")
    print(f"  Generating Hebrew TTS with Kisch voice ref...")

    try:
        # Try the multilingual TTS endpoint
        result = await fal_client.run_async("fal-ai/chatterbox/multilingual", arguments={
            "text": hebrew_text,
            "language": "he",
            "audio_prompt_url": ref_url,
        })

        print(f"  Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

        audio_out = result.get("audio", {}).get("url") if isinstance(result, dict) else None
        if audio_out:
            async with httpx.AsyncClient(timeout=120.0) as http:
                resp = await http.get(audio_out)
                out_path = OUTPUT_DIR / "chatterbox_tts_hebrew_test.wav"
                out_path.write_bytes(resp.content)
                print(f"  Saved to {out_path} ({len(resp.content):,} bytes)")
                print(f"  SUCCESS!")
        else:
            print(f"  Full result: {result}")

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# MAIN
# ============================================================================

async def main():
    print("=" * 60)
    print("Voice API Test Suite")
    print("=" * 60)
    print(f"Source audio: {SOURCE_AUDIO}")
    print(f"Target voice ref: {TARGET_REF}")

    await test_resemble_api()
    await test_chatterbox_fal()
    await test_chatterbox_tts()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print(f"Results in: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
