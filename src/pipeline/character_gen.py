"""Character image generation — Nano Banana Pro primary, FLUX Kontext fallback.

1. No reference image → Nano Banana Pro (text-only). Cheap, fast.

2. With a reference photo → Nano Banana Pro (ref) is tried FIRST.
   If Google's safety filter blocks the request (most often: real-photo refs
   of women + caricature prompts), we fall back to FLUX Kontext Pro on fal.ai,
   which has gentler filtering.

Both routes save the result under characters/_candidates/<slug>/option_N.png.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

import fal_client
import httpx
from google import genai
from google.genai import types


# Re-exported from scripts/character_lab.py — same prompt builder
from scripts.character_lab import build_prompt

log = logging.getLogger("mind-video")


# ----------------------------------------------------------------------------
# Route 1: text-only via Nano Banana Pro (existing behavior, kept for parity)
# ----------------------------------------------------------------------------

async def generate_text_only(
    description: str,
    style: str,
    output_path: Path,
    *,
    google_api_key: str,
) -> Path:
    """Generate one candidate image from text only (no reference image)."""
    if not google_api_key:
        raise RuntimeError("Nano Banana Pro requires google_api_key")
    client = genai.Client(api_key=google_api_key)
    prompt = build_prompt(description, style)
    response = client.models.generate_content(
        model="nano-banana-pro-preview",
        contents=[prompt],
        config=types.GenerateContentConfig(response_modalities=["image", "text"]),
    )
    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            output_path.write_bytes(part.inline_data.data)
            return output_path
    raise RuntimeError(f"Nano Banana Pro returned no image for {output_path.name}")


# ----------------------------------------------------------------------------
# Route 2a: reference image via Nano Banana Pro (preferred)
# ----------------------------------------------------------------------------

# Shared instruction template — used for both Nano Banana with ref and FLUX
# Kontext. Same wording so the two routes produce comparable output.
_REF_PROMPT_TEMPLATE = (
    "This same person from the reference image, but transformed into the "
    "following style: {style_clause} "
    "Keep the same face and identity but render in the new style. "
    "Vertical 9:16 portrait, chest up, looking slightly toward the camera, "
    "no hands near the face, mouth fully visible and clearly defined, "
    "eyes well-lit, plain background, no text or watermarks."
)


def is_google_safety_error(exc: BaseException) -> bool:
    """Return True if a Google AI exception was triggered by the safety filter
    or a content-moderation block — the case where FLUX Kontext is the
    appropriate fallback."""
    msg = str(exc).upper()
    return "SAFETY" in msg or "BLOCKED" in msg or "PROHIBITED_CONTENT" in msg


async def generate_with_ref_nano_banana(
    ref_image_path: Path,
    description: str,
    style: str,
    output_path: Path,
    *,
    google_api_key: str,
) -> Path:
    """Generate one candidate using Nano Banana Pro with a reference image.

    Raises on safety-filter blocks; caller should fall back to FLUX Kontext.
    """
    if not google_api_key:
        raise RuntimeError("Nano Banana Pro requires google_api_key")
    if not ref_image_path.exists():
        raise FileNotFoundError(f"Reference image missing: {ref_image_path}")

    log.info("generate_with_ref_nano_banana style=%s ref=%s",
             style, ref_image_path.name)
    client = genai.Client(api_key=google_api_key)

    ref_bytes = ref_image_path.read_bytes()
    mime = "image/png" if ref_image_path.suffix.lower() == ".png" else "image/jpeg"
    prompt = _REF_PROMPT_TEMPLATE.format(style_clause=_style_clause(style))
    if description:
        prompt = f"{prompt} Character description for additional context: {description}"

    response = client.models.generate_content(
        model="nano-banana-pro-preview",
        contents=[
            types.Part.from_bytes(data=ref_bytes, mime_type=mime),
            prompt,
        ],
        config=types.GenerateContentConfig(response_modalities=["image", "text"]),
    )
    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            output_path.write_bytes(part.inline_data.data)
            log.info("generate_with_ref_nano_banana OK style=%s bytes=%d",
                     style, len(part.inline_data.data))
            return output_path
    raise RuntimeError(
        f"Nano Banana Pro returned no image for {output_path.name} "
        f"(possibly safety-blocked, raw response: {response})"
    )


# ----------------------------------------------------------------------------
# Route 2b: reference image via FLUX Kontext Pro (fallback when Nano Banana
#           safety-blocks the request)
# ----------------------------------------------------------------------------


def _style_clause(style: str) -> str:
    """Produce the style-specific clause for the FLUX Kontext prompt.

    We re-use the STYLE_PRESETS dict from character_lab so the descriptors
    stay consistent across both routes.
    """
    from scripts.character_lab import STYLE_PRESETS
    style_lower = style.strip().lower().replace("-", "_").replace(" ", "_")
    preset = STYLE_PRESETS.get(style_lower)
    if preset:
        return preset
    return f"rendered in {style} style."


async def generate_with_ref(
    ref_image_path: Path,
    description: str,
    style: str,
    output_path: Path,
    *,
    fal_key: str,
) -> Path:
    """Generate one candidate using FLUX Kontext Pro with a reference image."""
    if not fal_key:
        raise RuntimeError("FLUX Kontext requires fal_key")
    if not ref_image_path.exists():
        raise FileNotFoundError(f"Reference image missing: {ref_image_path}")

    log.info("generate_with_ref style=%s ref=%s", style, ref_image_path.name)
    client = fal_client.AsyncClient(key=fal_key)

    # Upload the reference; fal returns a CDN URL we can pass to the model.
    try:
        ref_url = await client.upload_file(str(ref_image_path))
    except Exception:
        log.exception("generate_with_ref: upload_file raised")
        raise

    prompt = _REF_PROMPT_TEMPLATE.format(style_clause=_style_clause(style))
    if description:
        prompt = f"{prompt} Character description for additional context: {description}"

    try:
        handler = await client.submit(
            "fal-ai/flux-pro/kontext",
            arguments={
                "image_url": ref_url,
                "prompt": prompt,
                "aspect_ratio": "9:16",
                "guidance_scale": 3.5,
                "num_inference_steps": 28,
                "safety_tolerance": "5",
            },
        )
    except Exception:
        log.exception("generate_with_ref: submit raised")
        raise

    # Poll until done. Typical FLUX Kontext runtime: 6-15s.
    while True:
        status = await handler.status()
        if isinstance(status, fal_client.Completed):
            break
        await asyncio.sleep(1.5)

    result = await handler.get()
    images = result.get("images") or []
    if not images:
        log.warning("FLUX Kontext returned no images: %s", result)
        raise RuntimeError(f"FLUX Kontext returned no image: {result}")
    image_url = images[0].get("url")
    if not image_url:
        raise RuntimeError(f"FLUX Kontext result missing url: {images[0]}")

    async with httpx.AsyncClient(timeout=120.0) as http:
        resp = await http.get(image_url)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
    log.info("generate_with_ref OK style=%s bytes=%d", style, len(resp.content))
    return output_path
