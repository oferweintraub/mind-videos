"""Shared pipeline functions for episode generation.

Used by the local Streamlit UI (app.py) and reusable from any script.
Each function is idempotent: skips if the output file already exists.
"""

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Callable, Optional

import httpx
import fal_client
from google import genai
from google.genai import types

if "FAL_KEY" not in os.environ and "FAL_API_KEY" in os.environ:
    os.environ["FAL_KEY"] = os.environ["FAL_API_KEY"]


async def generate_image(prompt: str, output_path: Path) -> Path:
    output_path = Path(output_path)
    if output_path.exists():
        return output_path
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    response = client.models.generate_content(
        model="nano-banana-pro-preview",
        contents=[prompt],
        config=types.GenerateContentConfig(response_modalities=["image", "text"]),
    )
    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            output_path.write_bytes(part.inline_data.data)
            return output_path
    raise RuntimeError("Nano Banana Pro returned no image data")


async def generate_tts(
    text: str,
    voice_id: str,
    output_path: Path,
    stability: float = 0.5,
    similarity: float = 0.8,
    style: float = 0.3,
    tempo: float = 1.0,
) -> Path:
    output_path = Path(output_path)
    if output_path.exists():
        return output_path
    raw = output_path.parent / f"{output_path.stem}_raw.mp3"

    if not raw.exists():
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
                json={
                    "text": text,
                    "model_id": "eleven_v3",
                    "language_code": "he",
                    "voice_settings": {
                        "stability": stability,
                        "similarity_boost": similarity,
                        "style": style,
                    },
                },
            )
            r.raise_for_status()
            raw.write_bytes(r.content)

    if tempo != 1.0:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(raw),
            "-filter:a", f"atempo={tempo}",
            str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg atempo failed for {raw}")
    else:
        shutil.copy2(raw, output_path)
    return output_path


async def lipsync(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> Path:
    """VEED Fabric 1.0 lip-sync. progress_cb(elapsed_seconds, message) called each ~1s."""
    output_path = Path(output_path)
    if output_path.exists():
        return output_path

    img_url = await fal_client.upload_file_async(str(image_path))
    aud_url = await fal_client.upload_file_async(str(audio_path))
    handler = await fal_client.submit_async(
        "veed/fabric-1.0",
        arguments={
            "image_url": img_url,
            "audio_url": aud_url,
            "resolution": "480p",
        },
    )

    start = time.time()
    last_msg = "uploading"
    last_status_check = 0.0
    while True:
        now = time.time()
        elapsed = now - start

        # Poll fal.ai every ~8s (their guidance), tick UI every ~1s
        if now - last_status_check >= 8.0 or last_status_check == 0.0:
            status = await handler.status()
            last_status_check = now
            if isinstance(status, fal_client.Completed):
                if progress_cb:
                    progress_cb(elapsed, "complete")
                break
            if isinstance(status, fal_client.InProgress) and status.logs:
                last = status.logs[-1]
                last_msg = last.get("message", last_msg)[:80] if isinstance(last, dict) else str(last)[:80]

        if progress_cb:
            progress_cb(elapsed, last_msg)
        await asyncio.sleep(1)

    result = await handler.get()
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(result["video"]["url"])
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
    return output_path


async def concat(video_paths: list, output_path: Path) -> Path:
    output_path = Path(output_path)
    if output_path.exists():
        return output_path
    lst = output_path.parent / f"{output_path.stem}_list.txt"
    with open(lst, "w") as f:
        for vp in video_paths:
            f.write(f"file '{Path(vp).resolve()}'\n")

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(lst), "-c", "copy", str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.wait()
    if proc.returncode != 0:
        # Fall back to re-encode (codec mismatch between segments)
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(lst),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        if proc.returncode != 0:
            raise RuntimeError("ffmpeg concat failed even with re-encode")
    lst.unlink(missing_ok=True)
    return output_path
