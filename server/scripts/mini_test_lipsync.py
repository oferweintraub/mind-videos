#!/usr/bin/env python3
"""Minimal test for fal.ai lip-sync video generation.

Tests the full pipeline:
1. Load a small image
2. Generate ~4 seconds of Hebrew audio
3. Generate video with lip-sync via fal.ai VEED Fabric
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


async def test_audio_only():
    """Test audio generation separately."""
    from src.providers.audio.elevenlabs import ElevenLabsProvider

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY not set")
        return None, None

    provider = ElevenLabsProvider(api_key=api_key, emotion="neutral")

    text = "שלום שלום לכולם אנשים"
    print(f"Generating audio for: {text}")

    output_dir = Path("output/mini_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / "test_audio.mp3"

    try:
        audio_bytes, duration = await provider.generate_speech(
            text=text,
            output_path=audio_path,
        )
        print(f"Audio generated: {len(audio_bytes)} bytes, {duration:.2f}s")
        print(f"Saved to: {audio_path}")
        return audio_bytes, duration
    except Exception as e:
        print(f"Audio generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None
    finally:
        await provider.close()


async def test_video_generation(image_bytes: bytes, audio_bytes: bytes):
    """Test video generation with fal.ai."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if not api_key:
        print("ERROR: FAL_KEY not set")
        return None

    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    output_dir = Path("output/mini_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n--- Uploading image to fal.ai ---")
    image_url = await fal_client.upload_async(image_bytes, content_type="image/png")
    print(f"Image URL: {image_url}")

    print("\n--- Uploading audio to fal.ai ---")
    audio_url = await fal_client.upload_async(audio_bytes, content_type="audio/mpeg")
    print(f"Audio URL: {audio_url}")

    print("\n--- Submitting job to VEED Fabric ---")
    payload = {
        "image_url": image_url,
        "audio_url": audio_url,
        "resolution": "480p",
    }
    print(f"Payload: {payload}")

    try:
        # Submit job
        handle = await fal_client.submit_async(
            "veed/fabric-1.0",
            arguments=payload,
        )
        request_id = handle.request_id
        print(f"Job submitted: {request_id}")

        # Poll for status
        print("\n--- Polling for status ---")
        max_wait = 300  # 5 minutes
        poll_interval = 5
        elapsed = 0

        while elapsed < max_wait:
            status = await fal_client.status_async(
                "veed/fabric-1.0",
                request_id,
                with_logs=True,
            )

            status_type = type(status).__name__
            print(f"Status [{elapsed}s]: {status_type}")

            if hasattr(status, 'logs') and status.logs:
                for log in status.logs[-3:]:  # Show last 3 logs
                    print(f"  Log: {log}")

            if isinstance(status, fal_client.Completed):
                print("\n--- Job completed! ---")
                break
            elif hasattr(status, 'error') and status.error:
                print(f"\n--- Job failed: {status.error} ---")
                return None

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        else:
            print(f"\n--- Timeout after {max_wait}s ---")
            return None

        # Get result
        print("\n--- Fetching result ---")
        result = await fal_client.result_async("veed/fabric-1.0", request_id)
        print(f"Result type: {type(result)}")
        print(f"Result: {result}")

        # Extract video URL
        video_url = None
        if hasattr(result, "video"):
            video_url = result.video.url if hasattr(result.video, "url") else result.video
        elif isinstance(result, dict):
            video_url = result.get("video", {}).get("url") or result.get("video_url")

        if not video_url:
            print("ERROR: Could not extract video URL from result")
            return None

        print(f"Video URL: {video_url}")

        # Download video
        print("\n--- Downloading video ---")
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(video_url)
            response.raise_for_status()
            video_bytes = response.content

        video_path = output_dir / "test_video.mp4"
        video_path.write_bytes(video_bytes)
        print(f"Video saved: {video_path} ({len(video_bytes)} bytes)")

        return video_bytes

    except Exception as e:
        print(f"\n--- Error during video generation ---")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run the minimal test."""
    print("=" * 60)
    print("MINIMAL LIP-SYNC TEST")
    print("=" * 60)

    # Use existing reference image
    image_path = Path("output/accountability_sephardic_20260126/ref_option_1.png")
    if not image_path.exists():
        # Fallback to any available image
        from glob import glob
        images = glob("output/**/ref_option_1.png", recursive=True)
        if images:
            image_path = Path(images[0])
        else:
            print("ERROR: No reference image found")
            return

    print(f"Using image: {image_path}")
    image_bytes = image_path.read_bytes()
    print(f"Image size: {len(image_bytes)} bytes")

    # Step 1: Generate audio
    print("\n" + "=" * 60)
    print("STEP 1: Generate Audio")
    print("=" * 60)
    audio_bytes, duration = await test_audio_only()

    if not audio_bytes:
        print("Failed to generate audio, stopping")
        return

    # Step 2: Generate video
    print("\n" + "=" * 60)
    print("STEP 2: Generate Video with Lip-Sync")
    print("=" * 60)
    video_bytes = await test_video_generation(image_bytes, audio_bytes)

    if video_bytes:
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print("Audio: output/mini_test/test_audio.mp3")
        print("Video: output/mini_test/test_video.mp4")
    else:
        print("\n" + "=" * 60)
        print("FAILED")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
