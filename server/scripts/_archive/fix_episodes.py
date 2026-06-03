#!/usr/bin/env python3
"""
Fix both episodes with updated text and images.
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

EDEN_IMAGE = Path("output/girl_options_v2/girl_v2b.png")


async def generate_tts(text, voice_id, output_path, stability=0.5, similarity=0.8, style=0.3, tempo=1.0):
    """Generate audio with optional tempo."""
    if output_path.exists():
        print(f"  SKIP audio {output_path.name}")
        return
    api_key = os.environ["ELEVENLABS_API_KEY"]
    raw = output_path.parent / f"{output_path.stem}_raw.mp3"

    print(f"  TTS: {output_path.name}...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key},
            json={
                "text": text,
                "model_id": "eleven_v3",
                "language_code": "he",
                "voice_settings": {"stability": stability, "similarity_boost": similarity, "style": style},
            },
        )
        r.raise_for_status()
        raw.write_bytes(r.content)

    if tempo != 1.0:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(raw), "-filter:a", f"atempo={tempo}", str(output_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
    else:
        shutil.copy2(raw, output_path)
    print(f"  ✓ {output_path.name}")


async def generate_image(prompt, output_path):
    """Generate image with Nano Banana Pro."""
    if output_path.exists():
        print(f"  SKIP image {output_path.name}")
        return
    api_key = os.environ["GOOGLE_API_KEY"]
    client = genai.Client(api_key=api_key)
    print(f"  Image: {output_path.name}...")
    response = client.models.generate_content(
        model="nano-banana-pro-preview",
        contents=[prompt],
        config=types.GenerateContentConfig(response_modalities=["image", "text"]),
    )
    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            output_path.write_bytes(part.inline_data.data)
            print(f"  ✓ {output_path.name}")
            return


async def lipsync(image_path, audio_path, output_path):
    """VEED Fabric lip-sync."""
    if output_path.exists():
        print(f"  SKIP video {output_path.name}")
        return
    print(f"  Lip-sync: {output_path.name}...")
    img_url = await fal_client.upload_file_async(str(image_path))
    aud_url = await fal_client.upload_file_async(str(audio_path))
    h = await fal_client.submit_async("veed/fabric-1.0",
        arguments={"image_url": img_url, "audio_url": aud_url, "resolution": "480p"})
    t = time.time()
    while True:
        s = await h.status()
        if isinstance(s, fal_client.Completed):
            print(f"  ✓ {output_path.name} ({time.time()-t:.0f}s)")
            break
        await asyncio.sleep(8)
    r = await h.get()
    async with httpx.AsyncClient(timeout=120) as c:
        resp = await c.get(r["video"]["url"])
        output_path.write_bytes(resp.content)


async def concat(video_paths, output_path):
    """FFmpeg concat."""
    lst = output_path.parent / "list.txt"
    with open(lst, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp.resolve()}'\n")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(output_path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
    lst.unlink(missing_ok=True)
    dur = os.popen(f"ffprobe -v quiet -show_entries format=duration -of csv=p=0 '{output_path}'").read().strip()
    print(f"  ✓ Final: {output_path} ({dur}s)")


# =============================================================
# PILOT V4 — hostages, shorter Eden
# =============================================================
async def fix_pilot():
    print("=" * 50)
    print("PILOT V4 — hostages (fixed Eden text)")
    print("=" * 50)

    src = Path("output/pilot_v3")
    dst = Path("output/pilot_v4")
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "audio").mkdir(exist_ok=True)
    (dst / "videos").mkdir(exist_ok=True)

    # Reuse anchor audio + video from v3
    for seg in ["anchor_female", "anchor_male"]:
        for ext in [".mp3"]:
            s = src / "audio" / f"{seg}{ext}"
            d = dst / "audio" / f"{seg}{ext}"
            if s.exists() and not d.exists():
                shutil.copy2(s, d)
        s = src / "videos" / f"{seg}.mp4"
        d = dst / "videos" / f"{seg}.mp4"
        if s.exists() and not d.exists():
            shutil.copy2(s, d)

    # New Eden audio
    await generate_tts(
        text=(
            "אמא, הוא אמר שלא משאירים אנשים מאחור, "
            "אבל את החטופים השארנו מאחור, השארנו שמונה מאות ימים. "
            "אמא, ארבעים ושישה מהם נרצחו במנהרות בעזה. "
            "אז למה הוא התכוון שלא משאירים אנשים מאחור? "
            "למה הוא התכוון אמא?"
        ),
        voice_id="cgSgspJ2msm6clMCkdW9",
        output_path=dst / "audio" / "eden.mp3",
        stability=0.55, similarity=0.7, style=0.25, tempo=1.0,
    )

    # New Eden video
    await lipsync(EDEN_IMAGE, dst / "audio" / "eden.mp3", dst / "videos" / "eden.mp4")

    # Concat
    await concat([
        dst / "videos" / "anchor_female.mp4",
        dst / "videos" / "anchor_male.mp4",
        dst / "videos" / "eden.mp4",
    ], dst / "final.mp4")


# =============================================================
# EP02 V2 — victory (fixed anchor image, texts)
# =============================================================
async def fix_ep02():
    print()
    print("=" * 50)
    print("EP02 V2 — victory (love-struck anchor, fixed texts)")
    print("=" * 50)

    src = Path("output/ep02_victory")
    dst = Path("output/ep02_v2")
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "audio").mkdir(exist_ok=True)
    (dst / "videos").mkdir(exist_ok=True)
    (dst / "images").mkdir(exist_ok=True)

    # --- New love-struck female anchor image ---
    await generate_image(
        (
            "Generate a 9:16 image of a young Israeli Sephardic/Mizrahi woman TV news anchor "
            "in her early 30s, sitting behind a professional TV news desk. "
            "Dark olive skin, big dark eyes with heavy dramatic makeup, "
            "long straight dark hair, gold hoop earrings, "
            "wearing a tight black top with large number '14' printed on it. "
            "She has a love-struck dreamy expression, eyes sparkling and glowing with hearts, "
            "hands clasped together near her face, swooning, sighing with adoration, "
            "like a teenage girl seeing her crush. "
            "Behind her '14 חדשות' on screen. Blue studio lighting. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
        dst / "images" / "anchor_female_inlove.png",
    )

    # Reuse male anchor image from ep02
    male_img = src / "images" / "anchor_male_desk.png"
    dst_male_img = dst / "images" / "anchor_male_desk.png"
    if male_img.exists() and not dst_male_img.exists():
        shutil.copy2(male_img, dst_male_img)

    # --- Audio ---

    # Female 1 — same text, reuse
    f1_src = src / "audio" / "anchor_female_1.mp3"
    f1_dst = dst / "audio" / "anchor_female_1.mp3"
    if f1_src.exists() and not f1_dst.exists():
        shutil.copy2(f1_src, f1_dst)

    # Male 1 — NEW text (קוקו סבזי)
    await generate_tts(
        text=(
            "לגמרי! באיראן השמדנו הכל! "
            "לא נשאר להם אושפלאו או קוקו סבזי!"
        ),
        voice_id="IKne3meq5aSn9XLyUdCD",
        output_path=dst / "audio" / "anchor_male_1.mp3",
        stability=0.20, similarity=0.75, style=0.90, tempo=1.25,
    )

    # Female 2 — same text, reuse
    f2_src = src / "audio" / "anchor_female_2.mp3"
    f2_dst = dst / "audio" / "anchor_female_2.mp3"
    if f2_src.exists() and not f2_dst.exists():
        shutil.copy2(f2_src, f2_dst)

    # Male 2 — same text, reuse
    m2_src = src / "audio" / "anchor_male_2.mp3"
    m2_dst = dst / "audio" / "anchor_male_2.mp3"
    if m2_src.exists() and not m2_dst.exists():
        shutil.copy2(m2_src, m2_dst)

    # Eden — NEW text (removed Iran line, new ending)
    await generate_tts(
        text=(
            "אבל אמא, החמאס בעזה נשאר, לא? "
            "החיזבאללה ממשיכים עם הטילים וכל הצפון מופגז. "
            "אמא, ככה נראה ניצחון מוחלט? ככה נראה ביטחון? "
            "זה אנחנו ניצחנו אמא?"
        ),
        voice_id="cgSgspJ2msm6clMCkdW9",
        output_path=dst / "audio" / "eden.mp3",
        stability=0.55, similarity=0.7, style=0.25, tempo=1.0,
    )

    # --- Videos ---

    # Female 1 — NEW image (love-struck) + same audio
    await lipsync(
        dst / "images" / "anchor_female_inlove.png",
        dst / "audio" / "anchor_female_1.mp3",
        dst / "videos" / "anchor_female_1.mp4",
    )

    # Male 1 — same image + NEW audio
    await lipsync(
        dst_male_img,
        dst / "audio" / "anchor_male_1.mp3",
        dst / "videos" / "anchor_male_1.mp4",
    )

    # Female 2 — NEW image (love-struck) + same audio
    await lipsync(
        dst / "images" / "anchor_female_inlove.png",
        dst / "audio" / "anchor_female_2.mp3",
        dst / "videos" / "anchor_female_2.mp4",
    )

    # Male 2 — reuse from ep02
    m2v_src = src / "videos" / "anchor_male_2.mp4"
    m2v_dst = dst / "videos" / "anchor_male_2.mp4"
    if m2v_src.exists() and not m2v_dst.exists():
        shutil.copy2(m2v_src, m2v_dst)

    # Eden — NEW audio
    await lipsync(EDEN_IMAGE, dst / "audio" / "eden.mp3", dst / "videos" / "eden.mp4")

    # --- Concat ---
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
