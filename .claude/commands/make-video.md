---
description: Render a script.md end-to-end into a final.mp4
argument-hint: <episode-slug> | <path/to/script.md>
---

The user wants to render an episode end-to-end.

User input: **$ARGUMENTS**

## Step 1 — Resolve target

`$ARGUMENTS` is either a slug (look up `episodes/<slug>/script.md`) or an explicit path to a `.md` file. The runner handles both. If `$ARGUMENTS` is empty, ask the user which episode to render and run `ls episodes/` to show available ones.

## Step 2 — Preflight

Check that:
- `.env` has `FAL_KEY` and `ELEVENLABS_API_KEY` set (run `grep -E "^(FAL_KEY|ELEVENLABS_API_KEY)=" .env` — if either is empty, tell the user).
- `ffmpeg` is on the PATH (`ffmpeg -version` succeeds).
- The script's referenced characters all exist in `characters/`.

If any of these fail, stop and tell the user how to fix.

## Step 3 — Estimate cost

Read the script and roughly estimate cost:

```bash
source venv/bin/activate && python -c "
from src.script_format import parse_file
s = parse_file('<resolved path>')
total_chars = sum(len(seg.text) for seg in s.segments)
audio_sec = total_chars / 15
cost = audio_sec * 0.08 + 0.10 * len(s.segments)
print(f'~{audio_sec:.0f}s audio, {len(s.segments)} segments, ~\${cost:.2f}, ~{audio_sec*15/60:.0f}min wallclock')
"
```

Tell the user the estimate and ask: **"Proceed? (y/n)"** — unless the user has already authorized this run with phrases like "go ahead", "render it", "yes do it".

## Step 4 — Run the pipeline

```bash
# By slug (positional):
source venv/bin/activate && python scripts/make_episode.py <slug>

# Or with --episode flag (equivalent — useful if you're scripting):
source venv/bin/activate && python scripts/make_episode.py --episode <slug>

# Or pass an explicit script.md path:
source venv/bin/activate && python scripts/make_episode.py path/to/script.md
```

The runner prints progress to stdout — let it stream. Each segment goes through three steps:
1. **TTS** (ElevenLabs, ~5-15s per segment)
2. **Lip-sync** (VEED Fabric 1.0 via fal.ai, ~15s per second of audio)
3. **Concat** (ffmpeg, instant)

The pipeline is **idempotent** — if it fails partway through and you re-run, it picks up from the last successful step. Don't manually delete `episodes/<slug>/audio/` or `videos/` unless the user explicitly wants to regenerate.

## Step 5 — Show the result

When the pipeline finishes successfully:

```bash
ls -lh episodes/<slug>/final.mp4
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 episodes/<slug>/final.mp4
```

Tell the user:

> ✓ Episode ready: `episodes/<slug>/final.mp4` (<duration>s, <size>)
>
> Open it: `open episodes/<slug>/final.mp4`
>
> To iterate on a single line, edit the script.md and re-run `/make-video <slug>` — only the changed segments will regenerate.

## Common failures

- **fal.ai 403** → balance exhausted. User must top up at https://fal.ai/dashboard/billing.
- **ElevenLabs 400 on `language_code='he'`** → user is on Free tier; `eleven_v3` requires Creator+ ($22/mo).
- **`ffmpeg atempo failed`** → ffmpeg install is broken (often a Homebrew x265/x264 dylib mismatch). Fix with `brew reinstall ffmpeg`.
- **"Character X not in characters/"** → the script references a slug that doesn't exist; either fix the script or run `/new-character` first.
