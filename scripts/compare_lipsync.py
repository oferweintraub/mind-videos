#!/usr/bin/env python3
"""Compare lip-sync providers for Hebrew audio quality on fal.ai.

Round 2: VEED Fabric (baseline) vs Kling Avatar v2 vs Sync Lipsync 1.9 vs MuseTalk.
LatentSync was tested in round 1 and rejected (poor quality).

Usage:
    python scripts/compare_lipsync.py                    # All 3 segments
    python scripts/compare_lipsync.py --segments 0       # Just segment 0
    python scripts/compare_lipsync.py --segments 0 2     # Segments 0 and 2
    python scripts/compare_lipsync.py --providers veed kling  # Subset of providers
"""

import argparse
import asyncio
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ASSET_DIR = Path("output/accountability_16x9_ref_20260126")
OUTPUT_DIR = Path("output/lipsync_comparison")

PROVIDERS = {
    "veed": {
        "model_id": "veed/fabric-1.0",
        "label": "VEED Fabric 1.0",
        "input_type": "image+audio",  # takes image directly
    },
    "kling": {
        "model_id": "fal-ai/kling-video/ai-avatar/v2/standard",
        "label": "Kling Avatar v2 Std",
        "input_type": "image+audio",  # takes image directly
    },
    "kling_pro": {
        "model_id": "fal-ai/kling-video/ai-avatar/v2/pro",
        "label": "Kling Avatar v2 Pro",
        "input_type": "image+audio",  # takes image directly
    },
    "sync19": {
        "model_id": "fal-ai/sync-lipsync",
        "label": "Sync Lipsync 1.9",
        "input_type": "video+audio",  # needs video input
    },
    "musetalk": {
        "model_id": "fal-ai/musetalk",
        "label": "MuseTalk",
        "input_type": "video+audio",  # needs video input
    },
}

ALL_PROVIDER_KEYS = list(PROVIDERS.keys())


def estimate_cost(provider_key: str, duration_sec: float) -> float:
    """Estimate cost based on fal.ai pricing (Feb 2026)."""
    if provider_key == "veed":
        return duration_sec * 0.08  # $0.08/s at 480p
    elif provider_key == "kling":
        return duration_sec * 0.0562  # $0.0562/s
    elif provider_key == "kling_pro":
        return duration_sec * 0.115  # $0.115/s
    elif provider_key == "sync19":
        return duration_sec * (0.70 / 60)  # $0.70/min
    elif provider_key == "musetalk":
        return 0.0  # listed as free
    return 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_audio_duration(audio_path: Path) -> float:
    """Get duration in seconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(audio_path),
        ],
        capture_output=True, text=True,
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def image_to_static_video(image_path: Path, duration: float, output_path: Path):
    """Convert a static image to a video of the given duration using FFmpeg."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-t", str(duration),
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", "25",
            str(output_path),
        ],
        capture_output=True, check=True,
    )
    print(f"  Static video created: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")


async def upload_to_fal(data: bytes, content_type: str) -> str:
    """Upload bytes to fal.ai CDN, return URL."""
    import fal_client
    url = await fal_client.upload_async(data, content_type=content_type)
    return url


async def run_fal_job(model_id: str, payload: dict, label: str, max_wait: int = 600) -> dict:
    """Submit a fal.ai job, poll until done, return result dict."""
    import fal_client

    print(f"  [{label}] Submitting job to {model_id}...")
    handle = await fal_client.submit_async(model_id, arguments=payload)
    request_id = handle.request_id
    print(f"  [{label}] Job ID: {request_id}")

    poll_interval = 5
    elapsed = 0

    while elapsed < max_wait:
        status = await fal_client.status_async(model_id, request_id, with_logs=True)
        status_type = type(status).__name__

        if isinstance(status, fal_client.Completed):
            print(f"  [{label}] Completed after {elapsed}s")
            break
        elif hasattr(status, "error") and status.error:
            print(f"  [{label}] FAILED: {status.error}")
            return {"error": str(status.error)}

        if elapsed % 30 == 0:
            print(f"  [{label}] Status: {status_type} ({elapsed}s)")

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    else:
        print(f"  [{label}] TIMEOUT after {max_wait}s")
        return {"error": "timeout"}

    result = await fal_client.result_async(model_id, request_id)
    return result


async def download_video(url: str, output_path: Path) -> bytes:
    """Download video from URL, save to disk."""
    import httpx
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        video_bytes = resp.content

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(video_bytes)
    print(f"  Saved: {output_path} ({len(video_bytes) / 1024:.0f} KB)")
    return video_bytes


def extract_video_url(result) -> str | None:
    """Extract video URL from fal.ai result (handles both object and dict)."""
    if hasattr(result, "video"):
        v = result.video
        return v.url if hasattr(v, "url") else v
    if isinstance(result, dict):
        vid = result.get("video", {})
        if isinstance(vid, dict):
            return vid.get("url")
        return result.get("video_url")
    return None


# ---------------------------------------------------------------------------
# Provider runners
# ---------------------------------------------------------------------------

async def run_provider(
    provider_key: str,
    image_url: str,
    audio_url: str,
    static_video_url: str | None,
    segment_dir: Path,
) -> dict:
    """Run a single provider and return result dict."""
    cfg = PROVIDERS[provider_key]
    model_id = cfg["model_id"]
    label = cfg["label"]
    input_type = cfg["input_type"]

    # Build payload based on input type
    if input_type == "image+audio":
        payload = {"image_url": image_url, "audio_url": audio_url}
        if provider_key == "veed":
            payload["resolution"] = "480p"
    elif input_type == "video+audio":
        if not static_video_url:
            return {"provider": provider_key, "error": "no static video URL", "wall_time": 0}
        if provider_key == "musetalk":
            payload = {"source_video_url": static_video_url, "audio_url": audio_url}
        elif provider_key == "sync19":
            payload = {
                "model": "lipsync-1.9.0-beta",
                "video_url": static_video_url,
                "audio_url": audio_url,
                "sync_mode": "cut_off",
            }
        else:
            payload = {"video_url": static_video_url, "audio_url": audio_url}

    t0 = time.time()
    result = await run_fal_job(model_id, payload, label)
    wall_time = time.time() - t0

    if isinstance(result, dict) and "error" in result:
        return {"provider": provider_key, "error": result["error"], "wall_time": wall_time}

    video_url = extract_video_url(result)
    if not video_url:
        return {"provider": provider_key, "error": "no video URL in result", "wall_time": wall_time}

    output_path = segment_dir / f"{provider_key}.mp4"
    await download_video(video_url, output_path)

    return {
        "provider": provider_key,
        "video_path": str(output_path),
        "video_url": video_url,
        "wall_time": wall_time,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def compare_segment(seg_idx: int, provider_keys: list[str]) -> dict:
    """Run all selected providers on one segment and return results."""
    import fal_client

    image_path = ASSET_DIR / f"segment_{seg_idx:02d}_image.png"
    audio_path = ASSET_DIR / f"segment_{seg_idx:02d}_audio.mp3"

    if not image_path.exists() or not audio_path.exists():
        print(f"\nSegment {seg_idx}: SKIPPED (files not found)")
        return {"segment": seg_idx, "error": "files not found"}

    duration = get_audio_duration(audio_path)
    segment_dir = OUTPUT_DIR / f"segment_{seg_idx:02d}"
    segment_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"SEGMENT {seg_idx}  |  Audio: {duration:.1f}s  |  Image: {image_path.name}")
    print(f"Providers: {', '.join(PROVIDERS[k]['label'] for k in provider_keys)}")
    print(f"{'=' * 60}")

    # ---- Upload shared assets ----
    print("\nUploading assets to fal.ai...")
    image_bytes = image_path.read_bytes()
    audio_bytes = audio_path.read_bytes()

    image_url = await upload_to_fal(image_bytes, "image/png")
    audio_url = await upload_to_fal(audio_bytes, "audio/mpeg")
    print(f"  Image URL: {image_url[:80]}...")
    print(f"  Audio URL: {audio_url[:80]}...")

    # ---- Prepare static video if any video+audio providers are selected ----
    needs_static_video = any(
        PROVIDERS[k]["input_type"] == "video+audio" for k in provider_keys
    )
    static_video_url = None

    if needs_static_video:
        print("\nCreating static video for video+audio providers...")
        static_video_path = segment_dir / "static_input.mp4"
        image_to_static_video(image_path, duration, static_video_path)
        # Upload it
        print("  Uploading static video to fal.ai...")
        static_video_bytes = static_video_path.read_bytes()
        static_video_url = await upload_to_fal(static_video_bytes, "video/mp4")
        print(f"  Static video URL: {static_video_url[:80]}...")

    # ---- Run all providers in parallel ----
    print(f"\nRunning {len(provider_keys)} providers in parallel...")
    tasks = [
        run_provider(key, image_url, audio_url, static_video_url, segment_dir)
        for key in provider_keys
    ]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle exceptions
    provider_results = {}
    for key, res in zip(provider_keys, results_list):
        if isinstance(res, Exception):
            provider_results[key] = {"provider": key, "error": str(res), "wall_time": 0}
        else:
            provider_results[key] = res

    # ---- Summary ----
    print(f"\n{'─' * 60}")
    print(f"Segment {seg_idx} Results  |  Audio: {duration:.1f}s")
    print(f"{'─' * 60}")
    print()
    print(f"  {'Provider':<22} {'Status':<8} {'Wall':>6}  {'Cost':>7}  File")
    print(f"  {'─'*22} {'─'*8} {'─'*6}  {'─'*7}  {'─'*30}")

    for key in provider_keys:
        r = provider_results[key]
        label = PROVIDERS[key]["label"]
        cost = estimate_cost(key, duration)

        if "error" in r:
            print(f"  {label:<22} {'FAIL':<8} {r['wall_time']:>5.0f}s  ${cost:>6.2f}  {r['error']}")
        else:
            print(f"  {label:<22} {'OK':<8} {r['wall_time']:>5.0f}s  ${cost:>6.2f}  {r['video_path']}")

    return {
        "segment": seg_idx,
        "duration": duration,
        "providers": provider_results,
        "costs": {k: estimate_cost(k, duration) for k in provider_keys},
    }


async def main():
    import fal_client

    parser = argparse.ArgumentParser(description="Compare lip-sync providers on Hebrew audio")
    parser.add_argument(
        "--segments", nargs="*", type=int, default=[0, 1, 2],
        help="Segment indices to compare (default: 0 1 2)",
    )
    parser.add_argument(
        "--providers", nargs="*", default=ALL_PROVIDER_KEYS,
        choices=ALL_PROVIDER_KEYS,
        help=f"Providers to test (default: all). Choices: {ALL_PROVIDER_KEYS}",
    )
    args = parser.parse_args()

    # Setup fal.ai
    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if not api_key:
        print("ERROR: FAL_KEY or FAL_API_KEY not set in .env")
        sys.exit(1)

    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("HEBREW LIP-SYNC COMPARISON (Round 2)")
    print("=" * 60)
    print(f"Assets    : {ASSET_DIR}")
    print(f"Output    : {OUTPUT_DIR}")
    print(f"Segments  : {args.segments}")
    print(f"Providers : {', '.join(PROVIDERS[k]['label'] for k in args.providers)}")

    # Estimate total cost upfront
    total_est = 0
    for seg_idx in args.segments:
        audio_path = ASSET_DIR / f"segment_{seg_idx:02d}_audio.mp3"
        if audio_path.exists():
            dur = get_audio_duration(audio_path)
            for k in args.providers:
                total_est += estimate_cost(k, dur)

    print(f"\nEstimated total cost: ${total_est:.2f}")
    print()

    # Run comparisons
    all_results = []
    for seg_idx in args.segments:
        result = await compare_segment(seg_idx, args.providers)
        all_results.append(result)

    # ---- Final summary ----
    print(f"\n{'=' * 60}")
    print("FINAL SUMMARY")
    print(f"{'=' * 60}")
    print()
    print(f"  {'Provider':<22} {'Total Cost':>10}  {'Status'}")
    print(f"  {'─'*22} {'─'*10}  {'─'*30}")

    totals = {k: 0.0 for k in args.providers}
    statuses = {k: [] for k in args.providers}

    for r in all_results:
        if "error" in r and isinstance(r["error"], str):
            continue
        for k in args.providers:
            totals[k] += r["costs"].get(k, 0)
            pr = r["providers"].get(k, {})
            statuses[k].append("OK" if "error" not in pr else "FAIL")

    for k in args.providers:
        label = PROVIDERS[k]["label"]
        status_str = " / ".join(statuses[k]) if statuses[k] else "—"
        print(f"  {label:<22} ${totals[k]:>9.2f}  {status_str}")

    veed_total = totals.get("veed", 0)
    if veed_total > 0:
        print()
        print("  Savings vs VEED Fabric:")
        for k in args.providers:
            if k == "veed":
                continue
            saving = veed_total - totals[k]
            pct = (saving / veed_total) * 100 if veed_total else 0
            print(f"    {PROVIDERS[k]['label']:<20}: ${saving:>+.2f} ({pct:>+.0f}%)")

    print()
    print(f"  Output files in: {OUTPUT_DIR}/")
    print(f"  Compare videos side-by-side to evaluate Hebrew lip-sync quality.")

    # Save results JSON
    results_path = OUTPUT_DIR / "comparison_results.json"
    serializable = []
    for r in all_results:
        sr = dict(r)
        if "providers" in sr:
            for k, v in sr["providers"].items():
                if isinstance(v, dict):
                    sr["providers"][k] = {kk: vv for kk, vv in v.items() if kk != "video_bytes"}
        serializable.append(sr)

    results_path.write_text(json.dumps(serializable, indent=2, default=str))
    print(f"  Results saved to: {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
