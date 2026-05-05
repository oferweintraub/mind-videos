# Mind Video — Hebrew Animated Video Pipeline

End-to-end pipeline for producing short (≈30-60s) animated talking-character videos. Designed to be **driven from inside Claude Code or Claude Cowork** via three slash commands — no Python knowledge required to operate it.

```
/new-character  →  generate 3 candidate stills, pick one, save it to the library
/new-script     →  draft a Hebrew dialogue across N characters into a script.md
/make-video     →  render that script.md to final.mp4 (TTS + lip-sync + concat)
```

The pipeline orchestrates three external services: **Google Nano Banana Pro** (images), **ElevenLabs v3** (Hebrew TTS), and **VEED Fabric 1.0** on fal.ai (lip-sync), then stitches with **FFmpeg**.

Two finished examples ship in [`examples/`](examples/) — both produced from this exact pipeline:

| File | Format | Duration |
|------|--------|----------|
| [`pilot_hostages.mp4`](examples/pilot_hostages.mp4) | 3 segments (♀ anchor → ♂ anchor → Eden) | 29.1s |
| [`ep02_victory.mp4`](examples/ep02_victory.mp4) | 5 segments | 30.6s |

---

## 1. Quick start (5 minutes)

### 1.1 Clone + install

```bash
git clone <this-private-repo>
cd mind-video
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # then edit .env with your three keys (next section)
```

You also need **FFmpeg** on `$PATH`:
- macOS: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`
- Windows: https://ffmpeg.org/download.html → add to PATH

### 1.2 API keys

Edit `.env` and paste:

| Key | Get it at | Required for | Tier |
|-----|-----------|--------------|------|
| `FAL_KEY` | https://fal.ai/dashboard/keys | Lip-sync (VEED Fabric 1.0) | **Paid balance required** — Free tier returns 403. Top up ~$10 to start |
| `ELEVENLABS_API_KEY` | https://elevenlabs.io/app/settings/api-keys | Hebrew TTS via `eleven_v3` | **Creator+ ($22/mo)** — Free/Starter tiers return 403 on `eleven_v3` |
| `GOOGLE_API_KEY` | https://aistudio.google.com/app/apikey | Image generation (Nano Banana Pro) | Free tier OK |

### 1.3 Smoke test

```bash
python scripts/mini_test_lipsync.py
```

If this writes a ~3s MP4 to `output/`, you're good.

### 1.4 Render the shipped example

The repo ships with one example episode and 3 pre-built characters:

```bash
python scripts/make_episode.py example_hostages
# → episodes/example_hostages/final.mp4
```

That's the entire pipeline run. Open the MP4 to confirm.

---

## 2. The three slash commands

If you have Claude Code or Claude Cowork open in this repo, the workflow is:

### 2.1 `/new-character "<description>"`

> /new-character a young woman with curly red hair, freckles, denim jacket, in lego style

Claude:
1. Picks a slug + style (asks you to confirm)
2. Runs `scripts/character_lab.py` — generates 3 candidate images via Nano Banana Pro (~60s, ~$0.12 total)
3. Shows you the 3 PNGs at `characters/_candidates/<slug>/option_{1,2,3}.png` and asks which one to keep
4. Asks for a voice ID (suggests stock options) + tempo + display name
5. Runs `scripts/save_character.py` — promotes the picked candidate to `characters/<slug>/`

After this, the character is reusable across any future script.

**Available styles** (preset prompt fragments — anything else is treated as free-text):

`south_park`, `lego`, `muppet`, `pixar`, `ghibli`, `comic`, `anime`

For more authentic style fidelity (e.g. "true Muppet felt look"), see [`docs/advanced-styles.md`](docs/advanced-styles.md) — it covers FLUX LoRA training, Cartoonify, Ghiblify, and other fal.ai routes that produce stronger style results at higher setup cost.

### 2.2 `/new-script <slug> [topic | --from <path>]`

> /new-script grandma_remembers a satirical piece about a politician forgetting his promises

Claude:
1. Lists the available characters from `characters/`
2. Asks who should appear and in what order
3. Drafts 3-5 Hebrew segments matching each character's personality
4. Shows you the draft and lets you revise
5. Saves to `episodes/<slug>/script.md` once approved
6. Validates the script against the character library

**Starting from an existing draft** — pass `--from <path>` to import a `.txt`, `.md`, `.docx`, or `.pdf`:

> /new-script my_draft --from ~/Documents/dialogue.docx

Claude extracts the text via `scripts/extract_text.py`, shows you the content, proposes a speaker mapping (e.g. *line 1 → @anchor_female, line 2 → @eden*) based on any speaker labels in the source, and asks you to confirm before saving. For `.doc` (old Word), `.rtf`, or Google Docs: convert to `.docx`/`.txt` first (the script tells you how if you point it at an unsupported format).

### 2.3 `/make-video <slug>`

> /make-video grandma_remembers

Claude:
1. Estimates cost (~$0.10 per second of audio)
2. Asks you to confirm
3. Runs `scripts/make_episode.py` — the pipeline:
   - **TTS** per segment (ElevenLabs `eleven_v3` Hebrew, ~5-15s each)
   - **Lip-sync** per segment (VEED Fabric 1.0, ~15s per second of audio)
   - **Concat** into one 9:16 MP4 (FFmpeg)
4. Shows the path to `episodes/<slug>/final.mp4`

The pipeline is **idempotent** — re-running with the same slug only regenerates segments whose `.mp3` or `.mp4` is missing. So iterating on a single line is cheap (just edit the `script.md` and re-run).

---

## 3. The local Streamlit app

If you don't have Claude Code/Cowork, there's a browser-based UI for the same workflow:

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. The app:
- Loads all characters from `characters/` automatically
- Defaults the cast to Channel 14 anchor♀ + anchor♂ + Eden if those slugs exist
- Lets you edit Hebrew text per segment (RTL textareas), add/remove segments
- Streams real-time progress (image ✓ / audio ✓ / lip-sync ⟳ with elapsed seconds)
- Plays the final MP4 inline + offers a download button

Output goes to `episodes/<your-name>/final.mp4`.

The Streamlit app uses the **same** `src/pipeline/episode.py` and `src/character.py` modules as the CLI, so anything built one way works the other.

### 3.1 Hosting it for collaborators (Streamlit Community Cloud, free)

1. Push the repo to GitHub.
2. Sign in at https://share.streamlit.io with GitHub.
3. **New app** → pick the repo, branch `master`, main file `app.py`.
4. **Advanced settings → Secrets** → paste:
   ```toml
   APP_PASSWORD = "<pick a shared password>"
   ```
5. **Deploy**. First boot ~3 min (installs `ffmpeg` from `packages.txt`).
6. Share the URL + password.

Collaborators see a password screen, then a sidebar where they paste their **own** API keys (so they spend their own fal.ai/ElevenLabs balance, not yours).

**Limits**: 1 GB RAM (fine), ephemeral filesystem (download MP4s immediately), app sleeps after ~7 days of inactivity.

---

## 4. Repo layout

```
mind-video/
├── characters/                  # Character library — one dir per character
│   ├── anchor_female/
│   │   ├── manifest.json        # voice + metadata
│   │   └── image.png            # the still used for lip-sync
│   ├── anchor_male/
│   ├── eden/
│   └── _candidates/             # gitignored work area for /new-character
├── episodes/                    # User scripts + their generated outputs
│   ├── example_hostages/
│   │   ├── script.md            # the input (you write this)
│   │   ├── audio/  videos/      # intermediates (gitignored)
│   │   └── final.mp4            # the output
│   └── <your-episode>/
├── scripts/                     # CLI tooling
│   ├── character_lab.py         # generate N candidate stills
│   ├── save_character.py        # promote candidate → library
│   ├── make_episode.py          # render script.md → final.mp4
│   ├── compare_lipsync.py       # 8-provider lip-sync benchmark
│   ├── mini_test_lipsync.py     # one-clip smoke test
│   └── _archive/                # historical one-off scripts
├── src/
│   ├── character.py             # Character/Voice dataclasses + loader
│   ├── script_format.py         # script.md parser
│   └── pipeline/episode.py      # generate_tts / lipsync / concat
├── .claude/commands/            # Slash commands for Claude Code/Cowork
│   ├── new-character.md
│   ├── new-script.md
│   └── make-video.md
├── docs/advanced-styles.md      # FLUX LoRA / Cartoonify / Ghiblify routes
├── examples/                    # Two finished example MP4s
├── app.py                       # Streamlit UI
├── lessons.md  TASKS.md         # Working notes
└── README.md
```

---

## 5. Script format

`episodes/<slug>/script.md`:

```markdown
---
title: My Episode Title
description: Optional one-liner
---

## anchor_female  (love-struck — annotation is free text, ignored)
אני מאוהבת! איזה מנהיג חזק יש לנו!

## anchor_male
לגמרי! לא נשאר להם אורז למרק!

## eden  (quiet)
אבל אמא, החטופים?
```

**Rules**:
- Each `## ` heading starts a new segment.
- The first word after `##` MUST be a character slug from `characters/`.
- Anything else on the heading line is annotation (helpful for humans, ignored by the pipeline).
- The same character may appear multiple times — each `##` is its own segment with its own audio + video.
- Hebrew text goes between headings. Multi-line is OK; lines are joined with `\n`.

---

## 6. How it works — the orchestration

```
┌──────────────────────────────────────────────┐
│  scripts/make_episode.py <slug>              │
│  • parse episodes/<slug>/script.md           │
│  • for each segment, run steps 1-3           │
│  • idempotent: skip any output that exists   │
└────────────────┬─────────────────────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
┌────────────────┐  ┌──────────────────┐
│ 1. TTS         │  │ 2. LIP-SYNC      │
│ ElevenLabs v3  │  │ VEED Fabric 1.0  │
│ Hebrew         │  │ via fal.ai       │
│ + atempo       │  │ $0.08/s, 480p    │
│ → seg_NN.mp3   │  │ → seg_NN.mp4     │
└────────────────┘  └──────────────────┘
                            │
                            ▼
            ┌────────────────────────────┐
            │ 3. CONCAT                  │
            │ ffmpeg -f concat -c copy   │
            │ (re-encode fallback)       │
            │ → final.mp4 (9:16)         │
            └────────────────────────────┘
```

Implementation notes (battle-tested — see `lessons.md`):
- VEED Fabric 1.0 was chosen after benchmarking 8 lip-sync providers on Hebrew (`scripts/compare_lipsync.py`). LatentSync, Sync 1.9, MuseTalk had visibly worse quality; Aurora is a 25%-pricier backup.
- `tempo=1.25` post-applied via `ffmpeg atempo` makes anchors sound urgent/manic; narrators stay at 1.0.
- Each line gets its own MP4 → individual lines can be regenerated cheaply by deleting one file and re-running.
- ElevenLabs `eleven_v3` is the only model that supports `language_code='he'` (`eleven_multilingual_v2` returns 400 on this).

---

## 7. Cost reference

| Step | Cost |
|------|------|
| Character candidate (Nano Banana Pro) | ~$0.04 / image |
| Hebrew TTS (ElevenLabs eleven_v3) | included in Creator plan ($22/mo) |
| Lip-sync (VEED Fabric 1.0) | $0.08/s of audio @ 480p |
| Concat (FFmpeg) | free |

A typical 30s episode with 3 segments: **~$3-5** (mostly lip-sync).

A typical character creation (3 candidates): **~$0.12**.

---

## 8. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `403` from fal.ai | Out of balance → top up at https://fal.ai/dashboard/billing |
| `400` from ElevenLabs on `language_code='he'` | You're on Free/Starter — `eleven_v3` requires Creator ($22/mo) |
| `ffmpeg atempo failed` | ffmpeg install is broken (often a Homebrew x265/x264 dylib mismatch). Fix: `brew reinstall ffmpeg` |
| Pipeline hangs / seems frozen | VEED Fabric ≈ 15s per second of audio. A 25s line takes ~4 min |
| Character looks different per segment | Re-pick a more iconic candidate. For high-consistency needs, switch to FLUX Kontext Pro — see `docs/advanced-styles.md` |
| Mouth not lip-syncing well | Image has hands near face or mouth covered. Re-pick or regenerate |
| ElevenLabs blocks a voice clone | Don't name the clone after a public figure (ToS). Use a generic label |

[`lessons.md`](lessons.md) catalogs every pitfall hit in production. [`TASKS.md`](TASKS.md) is the running checkpoint.
