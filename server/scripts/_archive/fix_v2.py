#!/usr/bin/env python3
"""
Fix round 2:
- Pilot: new puzzled/wonder Eden image
- Ep02: new male anchor 1 audio ("אורז למרק")
"""

import asyncio
import os
import sys
import time
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

import httpx
import fal_client
from google import genai
from google.genai import types

if "FAL_KEY" not in os.environ and "FAL_API_KEY" in os.environ:
    os.environ["FAL_KEY"] = os.environ["FAL_API_KEY"]

STYLE_SOUTHPARK = (
    "South Park cartoon style, flat 2D paper cutout animation, "
    "simple geometric shapes, thick black outlines, bright flat colors, "
    "construction-paper texture, Comedy Central South Park aesthetic"
)


async def generate_tts(text, voice_id, output_path, stability=0.5, similarity=0.8, style=0.3, tempo=1.0):
    if output_path.exists():
        print(f"  SKIP audio {output_path.name}"); return
    api_key = os.environ["ELEVENLABS_API_KEY"]
    raw = output_path.parent / f"{output_path.stem}_raw.mp3"
    print(f"  TTS: {output_path.name}...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key},
            json={"text": text, "model_id": "eleven_v3", "language_code": "he",
                  "voice_settings": {"stability": stability, "similarity_boost": similarity, "style": style}},
        )
        r.raise_for_status()
        raw.write_bytes(r.content)
    if tempo != 1.0:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(raw), "-filter:a", f"atempo={tempo}", str(output_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.wait()
    else:
        shutil.copy2(raw, output_path)
    print(f"  ✓ {output_path.name}")


async def generate_image(prompt, output_path):
    if output_path.exists():
        print(f"  SKIP image {output_path.name}"); return
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    print(f"  Image: {output_path.name}...")
    response = client.models.generate_content(
        model="nano-banana-pro-preview", contents=[prompt],
        config=types.GenerateContentConfig(response_modalities=["image", "text"]))
    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            output_path.write_bytes(part.inline_data.data)
            print(f"  ✓ {output_path.name}"); return


async def lipsync(image_path, audio_path, output_path):
    if output_path.exists():
        print(f"  SKIP video {output_path.name}"); return
    print(f"  Lip-sync: {output_path.name}...")
    img_url = await fal_client.upload_file_async(str(image_path))
    aud_url = await fal_client.upload_file_async(str(audio_path))
    h = await fal_client.submit_async("veed/fabric-1.0",
        arguments={"image_url": img_url, "audio_url": aud_url, "resolution": "480p"})
    t = time.time()
    while True:
        s = await h.status()
        if isinstance(s, fal_client.Completed):
            print(f"  ✓ {output_path.name} ({time.time()-t:.0f}s)"); break
        await asyncio.sleep(8)
    r = await h.get()
    async with httpx.AsyncClient(timeout=120) as c:
        resp = await c.get(r["video"]["url"]); output_path.write_bytes(resp.content)


async def concat(video_paths, output_path):
    lst = output_path.parent / "list.txt"
    with open(lst, "w") as f:
        for vp in video_paths: f.write(f"file '{vp.resolve()}'\n")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(output_path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.wait()
    lst.unlink(missing_ok=True)
    dur = os.popen(f"ffprobe -v quiet -show_entries format=duration -of csv=p=0 '{output_path}'").read().strip()
    print(f"  ✓ Final: {output_path} ({dur}s)")


async def fix_pilot():
    print("=" * 50)
    print("PILOT V5 — puzzled Eden face")
    print("=" * 50)

    src = Path("output/pilot_v4")
    dst = Path("output/pilot_v5")
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "audio").mkdir(exist_ok=True)
    (dst / "videos").mkdir(exist_ok=True)
    (dst / "images").mkdir(exist_ok=True)

    # Generate puzzled/wonder Eden image
    await generate_image(
        (
            "Generate a 9:16 image of an extremely cute and adorable 10-year-old Israeli girl, "
            "big warm brown eyes full of wonder and confusion, "
            "round soft face, rosy cheeks, small button nose, "
            "she has two dark braids with colorful mismatched hair ties, "
            "wearing pink pajamas with little stars, "
            "sitting on an orange couch holding a worn stuffed bunny, "
            "her expression is puzzled and questioning, eyebrows furrowed in confusion, "
            "mouth slightly open as if asking 'why?', head tilted to the side, "
            "NOT smiling, looking worried and confused, "
            "warm cozy Israeli living room with menorah on shelf. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
        dst / "images" / "eden_puzzled.png",
    )

    # Reuse anchor videos from v4
    for seg in ["anchor_female", "anchor_male"]:
        s = src / "videos" / f"{seg}.mp4"
        d = dst / "videos" / f"{seg}.mp4"
        if s.exists() and not d.exists():
            shutil.copy2(s, d)

    # Reuse Eden audio from v4
    s = src / "audio" / "eden.mp3"
    d = dst / "audio" / "eden.mp3"
    if s.exists() and not d.exists():
        shutil.copy2(s, d)

    # New Eden video with puzzled image
    await lipsync(
        dst / "images" / "eden_puzzled.png",
        dst / "audio" / "eden.mp3",
        dst / "videos" / "eden.mp4",
    )

    await concat([
        dst / "videos" / "anchor_female.mp4",
        dst / "videos" / "anchor_male.mp4",
        dst / "videos" / "eden.mp4",
    ], dst / "final.mp4")


async def fix_ep02():
    print()
    print("=" * 50)
    print("EP02 V3 — fixed male anchor text (אורז למרק)")
    print("=" * 50)

    src = Path("output/ep02_v2")
    dst = Path("output/ep02_v3")
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "audio").mkdir(exist_ok=True)
    (dst / "videos").mkdir(exist_ok=True)

    # New male 1 audio
    await generate_tts(
        text=(
            "לגמרי! באיראן השמדנו הכל! "
            "לא נשאר להם אפילו אורז למרק!"
        ),
        voice_id="IKne3meq5aSn9XLyUdCD",
        output_path=dst / "audio" / "anchor_male_1.mp3",
        stability=0.20, similarity=0.75, style=0.90, tempo=1.25,
    )

    # New male 1 video (same image, new audio)
    male_img = src / "images" / "anchor_male_desk.png"
    await lipsync(male_img, dst / "audio" / "anchor_male_1.mp3", dst / "videos" / "anchor_male_1.mp4")

    # Reuse everything else from ep02_v2
    for seg in ["anchor_female_1", "anchor_female_2", "anchor_male_2", "eden"]:
        s = src / "videos" / f"{seg}.mp4"
        d = dst / "videos" / f"{seg}.mp4"
        if s.exists() and not d.exists():
            shutil.copy2(s, d)

    await concat([
        dst / "videos" / "anchor_female_1.mp4",
        dst / "videos" / "anchor_male_1.mp4",
        dst / "videos" / "anchor_female_2.mp4",
        dst / "videos" / "anchor_male_2.mp4",
        dst / "videos" / "eden.mp4",
    ], dst / "final.mp4")


async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target in ("all", "pilot"):
        await fix_pilot()
    if target in ("all", "ep02"):
        await fix_ep02()
    print("\nDONE!")

if __name__ == "__main__":
    asyncio.run(main())
