> **FIRST ACTION EVERY SESSION**: Run `Read lessons.md` before any other work. Then read `TASKS.md` for current status.
> **Personal Context**: Read `~/OferW/oferw-self/index.md` for context about the developer. Consult relevant wiki pages as needed.

# Mind Video — Hebrew Animated Video Pipeline

Pipeline for short Hebrew animated talking-character videos. Designed to be operated end-to-end from inside Claude Code or Claude Cowork via three slash commands. The README is the user-facing entry point; this file is operating context for AI assistants.

## Canonical UX (slash commands)

| Command | What it does | Backing script |
|---------|--------------|----------------|
| `/new-character "<desc>"` | Generate 3 candidate stills, pick one, save to library | `scripts/character_lab.py` + `scripts/save_character.py` |
| `/new-script <slug> [topic]` | Draft a Hebrew dialogue across N characters | (no backing script — Claude writes the script.md) |
| `/make-video <slug>` | Render a script.md end-to-end to final.mp4 | `scripts/make_episode.py` |

The slash command files live at `.claude/commands/*.md` — **read them when the user invokes one**; they contain the precise step-by-step flow each command should follow.

## Repo Structure

```
characters/<slug>/
    manifest.json    # Character object: slug, display_name, description, style, voice settings
    image.png        # The still used for lip-sync (must show full face + clean mouth)
characters/_candidates/<slug>/
    option_*.png     # Work area; gitignored

episodes/<slug>/
    script.md        # User input — Markdown with `## <slug>` per segment
    audio/  videos/  # Intermediates (gitignored)
    final.mp4        # Output (gitignored)

scripts/
    character_lab.py        # Generate N candidate character stills via Nano Banana Pro
    save_character.py       # Promote a candidate → characters/<slug>/
    make_episode.py         # Parse script.md → run TTS+lipsync+concat → final.mp4
    compare_lipsync.py      # 8-provider lip-sync benchmark (reference)
    mini_test_lipsync.py    # Smoke test
    _archive/               # Historical one-off scripts (do not run)

src/
    character.py            # Character/Voice dataclasses + load() / list_all() / save()
    script_format.py        # parse(text) -> EpisodeScript with .segments and .meta
    pipeline/episode.py     # generate_image / generate_tts / lipsync / concat (idempotent)

app.py                      # Streamlit UI (loads characters from disk; mirrors the CLI flow)
docs/advanced-styles.md     # FLUX LoRA / Cartoonify / Ghiblify routes for stronger style fidelity
```

## Tech Stack

| Layer | Provider | Model / Endpoint |
|-------|----------|------------------|
| Images | Google AI | `nano-banana-pro-preview` |
| TTS (Hebrew) | ElevenLabs | `eleven_v3` with `language_code='he'` |
| Lip-sync (primary) | fal.ai | `veed/fabric-1.0`, $0.08/s, 480p |
| Lip-sync (fallback) | fal.ai | `fal-ai/creatify/aurora`, $0.10/s — only if VEED is down |
| Concat / atempo | local | `ffmpeg` |

**Stylized image alternatives** (covered in `docs/advanced-styles.md`, not on the default path):
- `fal-ai/flux-lora-fast-training` — train a custom puppet/Muppet LoRA, $2 one-time
- `fal-ai/cartoonify` — Pixar 3D from a photo
- `fal-ai/ghiblify` — Studio Ghibli watercolor
- `fal-ai/flux-pro/kontext` — strong cross-image character consistency
- `fal-ai/instant-character` — character from a single reference photo

**Benchmarked & rejected** lip-sync providers: LatentSync, Sync 1.9, MuseTalk (poor quality), Kling Avatar v2 (less sharp), OmniHuman v1.5 (too slow). See `scripts/compare_lipsync.py` for the harness.

## Critical implementation rules

1. **Always pass a reference image** when regenerating a character at a new pose / setting. Text-only generation drifts. The `Character.image_path` is the canonical reference; pass it as `types.Part.from_bytes(...)` to Nano Banana Pro.

2. **Image quality criteria for lip-sync** (lip-sync fails if any are missed):
   - No hands near the face
   - Mouth fully visible and clearly defined
   - Eyes well-lit
   - Plain or softly out-of-focus background; no text/captions/logos

3. **Pipeline is idempotent** — every step in `src/pipeline/episode.py` skips if its output exists. Don't add extra existence checks; trust the pipeline. To force regeneration, delete the specific file (not the whole episode dir — that loses cached audio you might still want).

4. **Tempo is per-character**, lives in `manifest.json -> voice.tempo`. Channel 14 anchors use `1.25` (manic urgency); narrators/children stay at `1.0`. Apply it via `ffmpeg atempo` in `generate_tts`.

5. **ElevenLabs Hebrew requires `eleven_v3`** + `language_code='he'`. `eleven_multilingual_v2` returns 400 on this. STS (speech-to-speech) does **not** preserve Hebrew — use Chatterbox S2S in `scripts/_archive/episode1_s2s.py` if you need voice conversion.

6. **fal.ai needs paid balance** — Free tier returns 403. ElevenLabs `eleven_v3` requires Creator+ ($22/mo) — Free/Starter return 403.

7. **Voice clones**: don't name a clone after a public figure (ElevenLabs ToS blocks this). Use generic names like "Hebrew Narrator Male v3".

## API Keys (all in `.env`)

```bash
FAL_KEY=               # fal.ai (lip-sync) — paid balance required
ELEVENLABS_API_KEY=    # ElevenLabs (TTS) — Creator+ tier required for eleven_v3
GOOGLE_API_KEY=        # Google AI Studio (Nano Banana Pro images) — Free tier OK
```

The Streamlit app additionally supports `APP_PASSWORD` (in `.streamlit/secrets.toml` or env) for shared-deployment auth.

## When the user asks you to do something

- **"Make a character"** → invoke the steps in `.claude/commands/new-character.md`. Do not skip the user-pick step. Generate 3 candidates, never 1.
- **"Write a script"** → invoke the steps in `.claude/commands/new-script.md`. List available characters first, then ask who appears.
- **"Render an episode"** → invoke the steps in `.claude/commands/make-video.md`. Estimate cost first, ask for go/no-go unless the user has already authorized.
- **"Add a new style not in the presets"** → it's likely a free-text style fed to Nano Banana Pro. If the user wants high fidelity (true Muppet felt, true Lego plastic), point them to `docs/advanced-styles.md` and offer to set up the LoRA path.
- **Anything in `scripts/_archive/`** → these are historical reference scripts; do not run them. They contain hardcoded paths and may not work with the current structure.
