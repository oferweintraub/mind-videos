"""Shared pipeline functions for episode generation.

Used by the local Streamlit UI (app.py) and reusable from any script.
Each function is idempotent: skips if the output file already exists.

API keys are passed as explicit keyword arguments so each call uses its
own caller-provided credentials. We deliberately do NOT read from
os.environ here — on multi-tenant deploys (Streamlit Cloud) os.environ is
process-global and would leak keys between concurrent users.
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

# Text-to-video model for generated animation scenes. Override via env without
# a code change if fal.ai renames the endpoint or you want a different tier.
KLING_T2V_ENDPOINT = os.environ.get(
    "KLING_T2V_ENDPOINT", "fal-ai/kling-video/v1.6/standard/text-to-video"
)


async def generate_image(
    prompt: str,
    output_path: Path,
    *,
    google_api_key: str,
) -> Path:
    output_path = Path(output_path)
    if output_path.exists():
        return output_path
    if not google_api_key:
        raise RuntimeError("generate_image requires google_api_key")
    client = genai.Client(api_key=google_api_key)
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
    *,
    elevenlabs_api_key: str,
    stability: float = 0.5,
    similarity: float = 0.8,
    style: float = 0.3,
    tempo: float = 1.0,
) -> Path:
    output_path = Path(output_path)
    if output_path.exists():
        return output_path
    if not elevenlabs_api_key:
        raise RuntimeError("generate_tts requires elevenlabs_api_key")
    raw = output_path.parent / f"{output_path.stem}_raw.mp3"

    if not raw.exists():
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={"xi-api-key": elevenlabs_api_key},
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
            if r.status_code == 404:
                raise RuntimeError(
                    f"ElevenLabs has no voice with id '{voice_id}'. Edit this "
                    f"character and pick a voice from the dropdown (or paste a "
                    f"valid ElevenLabs voice id)."
                )
            if r.status_code == 401:
                raise RuntimeError(
                    "ElevenLabs rejected the API key (401). Check ELEVENLABS_API_KEY."
                )
            if r.status_code >= 400:
                raise RuntimeError(
                    f"ElevenLabs TTS failed ({r.status_code}) for voice "
                    f"'{voice_id}': {r.text[:300]}"
                )
            raw.write_bytes(r.content)

    # Combine atempo (optional) and silence-trim in a single ffmpeg pass.
    # ElevenLabs eleven_v3 typically prepends 100-400ms of silence which VEED
    # Fabric renders as closed-mouth idle — feels like a lip-sync delay.
    # We only trim true leading + trailing silence — never mid-audio.
    #
    # NOTE: a naive `silenceremove=stop_periods=1:stop_silence=0.10` chops
    # everything after the FIRST 0.10s pause anywhere — Hebrew text with
    # commas/ellipses ends up truncated to under a second. The canonical
    # "trim ends only" pattern is: trim leading, reverse audio, trim leading
    # again (which is the original trailing), reverse back.
    filters: list[str] = []
    if tempo != 1.0:
        filters.append(f"atempo={tempo}")
    _edge_trim = "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-40dB"
    filters.extend([_edge_trim, "areverse", _edge_trim, "areverse"])
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(raw),
        "-af", ",".join(filters),
        str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        tail = stderr.decode(errors="replace").strip().splitlines()[-3:]
        raise RuntimeError(
            f"ffmpeg TTS post-process failed (exit {proc.returncode}): "
            + " | ".join(tail)
        )
    return output_path


async def lipsync(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    *,
    fal_key: str,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> Path:
    """VEED Fabric 1.0 lip-sync. progress_cb(elapsed_seconds, message) called each ~1s."""
    output_path = Path(output_path)
    if output_path.exists():
        return output_path
    if not fal_key:
        raise RuntimeError("lipsync requires fal_key")

    # Per-call client so each user's key stays scoped to their session.
    client = fal_client.AsyncClient(key=fal_key)

    img_url = await client.upload_file(str(image_path))
    aud_url = await client.upload_file(str(audio_path))
    handler = await client.submit(
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
    async with httpx.AsyncClient(timeout=120.0) as http_client:
        resp = await http_client.get(result["video"]["url"])
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
    return output_path


async def generate_animation(
    prompt: str,
    output_path: Path,
    *,
    fal_key: str,
    duration: int = 5,
    aspect_ratio: str = "16:9",
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> Path:
    """Generate a silent animation clip from a text prompt via Kling (fal.ai).

    Idempotent. progress_cb(elapsed_seconds, message) is called each ~1s, same
    contract as `lipsync` so callers can reuse their progress printer.
    """
    output_path = Path(output_path)
    if output_path.exists():
        return output_path
    if not fal_key:
        raise RuntimeError("generate_animation requires fal_key")
    if not prompt.strip():
        raise RuntimeError("generate_animation requires a non-empty prompt")

    client = fal_client.AsyncClient(key=fal_key)
    handler = await client.submit(
        KLING_T2V_ENDPOINT,
        arguments={
            "prompt": prompt,
            "duration": str(duration),
            "aspect_ratio": aspect_ratio,
        },
    )

    start = time.time()
    last_msg = "submitted"
    last_status_check = 0.0
    while True:
        now = time.time()
        elapsed = now - start
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
    async with httpx.AsyncClient(timeout=180.0) as http_client:
        resp = await http_client.get(result["video"]["url"])
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
    return output_path


async def _probe_duration(path: Path) -> float:
    """Media duration in seconds via ffprobe. Returns 0.0 on failure."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode(errors="replace").strip())
    except (ValueError, AttributeError):
        return 0.0


async def mux_audio_over_video(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
) -> Path:
    """Lay a narration track over a silent animation clip.

    The output runs as long as the LONGER of the two — the video freezes on its
    last frame if the narration is longer, and the audio is padded with silence
    if the clip is longer — so neither the visuals nor the narration get cut.
    Idempotent.
    """
    output_path = Path(output_path)
    if output_path.exists():
        return output_path

    v_dur = await _probe_duration(video_path)
    a_dur = await _probe_duration(audio_path)
    target = max(v_dur, a_dur)
    pad_v = max(0.0, target - v_dur)
    pad_a = max(0.0, target - a_dur)
    filter_complex = (
        f"[0:v]tpad=stop_duration={pad_v:.3f}:stop_mode=clone[v];"
        f"[1:a]apad=pad_dur={pad_a:.3f}[a]"
    )
    args = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
    ]
    if target > 0:
        args += ["-t", f"{target:.3f}"]
    args.append(str(output_path))

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        tail = stderr.decode(errors="replace").strip().splitlines()[-3:]
        raise RuntimeError(
            f"ffmpeg audio/video mux failed (exit {proc.returncode}): "
            + " | ".join(tail)
        )
    return output_path


async def _has_audio(path: Path) -> bool:
    """True if the file has at least one audio stream."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0", str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    return b"audio" in out


async def _ensure_audio(path: Path) -> Path:
    """Return a clip guaranteed to have an audio stream — adds a silent stereo
    track to clips that have none (e.g. narration-free scenes). Without this,
    `concat -c copy` drops audio for the ENTIRE video when any segment lacks it.
    """
    path = Path(path)
    if await _has_audio(path):
        return path
    fixed = path.parent / f"{path.stem}_silentaud.mp4"
    if not fixed.exists():
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-i", str(path),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            str(fixed),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode != 0 or not fixed.exists():
            return path  # best effort — fall back to the original
    return fixed


async def concat(video_paths: list, output_path: Path) -> Path:
    output_path = Path(output_path)
    # Normalize: every clip must carry an audio stream, else stream-copy concat
    # silently drops audio for the whole output.
    normalized = [await _ensure_audio(Path(vp)) for vp in video_paths]
    # Regenerate if the cached final is stale — i.e. any segment clip is newer
    # than it (a segment was added/changed/re-rendered). Without this, adding a
    # scene leaves the old final.mp4 in place and the new clip never appears.
    if output_path.exists():
        out_mtime = output_path.stat().st_mtime
        inputs_newer = any(
            Path(vp).exists() and Path(vp).stat().st_mtime > out_mtime for vp in normalized
        )
        if not inputs_newer:
            return output_path
        output_path.unlink(missing_ok=True)
    lst = output_path.parent / f"{output_path.stem}_list.txt"
    with open(lst, "w") as f:
        for vp in normalized:
            f.write(f"file '{Path(vp).resolve()}'\n")

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(lst), "-c", "copy", str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
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
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            tail = stderr.decode(errors="replace").strip().splitlines()[-3:]
            raise RuntimeError(
                f"ffmpeg concat failed (exit {proc.returncode}): "
                + " | ".join(tail)
            )
    lst.unlink(missing_ok=True)
    return output_path
