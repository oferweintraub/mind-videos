"""Friendly error messages — translate provider exceptions into actionable hints.

Pipeline failures (TTS / lip-sync / image gen) often surface as raw
HTTPStatusError or RuntimeError that mention 401/403/429 etc. End users
don't read those well. This module converts the common failure shapes
into prose explaining what to fix and where.
"""

from __future__ import annotations


def friendly_error(e: Exception) -> str:
    """Translate common pipeline errors into actionable hints (Markdown).

    Returns a Streamlit-friendly Markdown string ready to pass to st.error()
    or st.warning(). Falls back to a generic message that still keeps the
    technical exception visible.
    """
    msg = str(e)
    typename = type(e).__name__
    short = msg[:300]

    # ---------------- ElevenLabs ----------------
    if "elevenlabs.io" in msg and "401" in msg:
        return (
            "**ElevenLabs rejected the API key (401 Unauthorized).**\n\n"
            "Common causes:\n"
            "1. The key in the **Settings panel** is wrong, expired, or has trailing whitespace\n"
            "2. The key was revoked at https://elevenlabs.io/app/settings/api-keys\n\n"
            "Fix: open the Settings panel (left), click the eye icon to reveal the "
            "ElevenLabs key, paste it fresh from your account page, then retry.\n\n"
            f"<details><summary>Technical details</summary>\n\n`{typename}: {short}`</details>"
        )
    if "elevenlabs.io" in msg and "403" in msg:
        return (
            "**ElevenLabs returned 403 Forbidden.**\n\n"
            "Most likely: your account is on the **Free or Starter** tier. The Hebrew "
            "model (`eleven_v3`) requires the **Creator plan** ($22/mo) or higher. "
            "Upgrade at https://elevenlabs.io/app/subscription, then retry.\n\n"
            f"<details><summary>Technical details</summary>\n\n`{typename}: {short}`</details>"
        )
    if "elevenlabs.io" in msg and "429" in msg:
        return (
            "**ElevenLabs rate limit hit (429).**\n\n"
            "Wait ~60 seconds and retry. If this happens often, your tier's "
            "concurrency cap is the bottleneck — Creator allows 5 concurrent, "
            "Pro allows 10."
            f"\n\n<details><summary>Technical details</summary>\n\n`{typename}: {short}`</details>"
        )

    # ---------------- fal.ai ----------------
    if ("fal.ai" in msg or "fal.run" in msg or "fal-ai" in msg) and ("401" in msg or "403" in msg):
        return (
            "**fal.ai rejected the request.**\n\n"
            "Common causes:\n"
            "1. **Out of paid balance** — top up at https://fal.ai/dashboard/billing\n"
            "2. The key in the **Settings panel** is wrong or has trailing whitespace\n\n"
            "Fix one of those, then retry.\n\n"
            f"<details><summary>Technical details</summary>\n\n`{typename}: {short}`</details>"
        )
    if ("fal.ai" in msg or "fal.run" in msg) and "429" in msg:
        return (
            "**fal.ai rate limit hit (429).**\n\n"
            "Wait ~30 seconds and retry."
            f"\n\n<details><summary>Technical details</summary>\n\n`{typename}: {short}`</details>"
        )

    # ---------------- Google AI / Nano Banana Pro ----------------
    if "API_KEY_INVALID" in msg or (
        ("google" in msg.lower() or "generativelanguage" in msg)
        and ("401" in msg or "403" in msg)
    ):
        return (
            "**Google AI rejected the API key.**\n\n"
            "Common causes:\n"
            "1. The key in the **Settings panel** is wrong, expired, or has trailing whitespace\n"
            "2. The key doesn't have access to Nano Banana Pro (regenerate at "
            "https://aistudio.google.com/app/apikey)\n\n"
            "Fix and retry.\n\n"
            f"<details><summary>Technical details</summary>\n\n`{typename}: {short}`</details>"
        )
    if "RESOURCE_EXHAUSTED" in msg or ("quota" in msg.lower() and "google" in msg.lower()):
        return (
            "**Google AI quota exceeded.**\n\n"
            "You've hit the free-tier rate limit on Nano Banana Pro. Wait ~60 seconds "
            "and retry, or enable billing at https://console.cloud.google.com/billing "
            "for higher quotas."
            f"\n\n<details><summary>Technical details</summary>\n\n`{typename}: {short}`</details>"
        )
    if "SAFETY" in msg.upper() or "blocked" in msg.lower() and "google" in msg.lower():
        return (
            "**Google AI safety filter blocked the request.**\n\n"
            "The description triggered Google's content moderation. This is most "
            "common with: photo refs of real people + caricature/stylization prompts, "
            "or descriptions involving children with violent themes. Try rewording "
            "the description more neutrally, or upload a reference image and use "
            "FLUX Kontext (which has gentler filtering).\n\n"
            f"<details><summary>Technical details</summary>\n\n`{typename}: {short}`</details>"
        )

    # ---------------- ffmpeg ----------------
    if "ffmpeg" in msg.lower():
        return (
            "**ffmpeg returned an error.**\n\n"
            "This is usually transient. Click retry — the pipeline is idempotent "
            "and resumes from cached steps.\n\n"
            f"<details><summary>Technical details</summary>\n\n`{typename}: {short[:400]}`</details>"
        )

    # ---------------- Network ----------------
    if any(k in msg.lower() for k in ("timeout", "connection", "dns")):
        return (
            "**Network error.**\n\n"
            "Could be transient (cloud-side blip) or your network. Wait 30 seconds "
            "and retry.\n\n"
            f"<details><summary>Technical details</summary>\n\n`{typename}: {short}`</details>"
        )

    # ---------------- Fallback ----------------
    return (
        f"**Operation failed**: `{typename}: {short}`\n\n"
        "The pipeline is idempotent — anything successfully generated is cached. "
        "Click retry to resume from where it stopped."
    )
