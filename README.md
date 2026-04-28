# Mind Video — Hebrew Satirical Video Pipeline

Automated pipeline for producing short (≈30-60s) Hebrew satirical videos in the **"בגדי המלך החדשים"** ("The Emperor's New Clothes") format — Channel 14-style anchors enthusiastically delivering a piece of state propaganda, then cutting to **Eden**, a 7-8 year old girl who asks one innocent question that collapses the whole narrative.

The pipeline is fully orchestrated: a Python script defines the script + characters, three external services produce stills/voice/lip-sync, and FFmpeg stitches the result into a single 9:16 MP4 ready for social posting.

---

## 1. What this does

You write a **script** (Hebrew text + which character speaks each line) and a **character description** (Channel 14 anchors and Eden are pre-built — see below). The pipeline produces a final stitched video by:

1. Generating a **South Park-style cartoon still** for each speaking character via Google's **Nano Banana Pro**.
2. Running each line through **ElevenLabs v3 Hebrew TTS** with a per-character voice + emotion + tempo.
3. Sending each (still + audio) pair to **VEED Fabric 1.0** (or Aurora as a fallback) for lip-synced video.
4. Concatenating all clips with **FFmpeg** into a final `final.mp4`.

Two finished examples ship in [`examples/`](examples/):

| File | Format | Duration | Theme |
|------|--------|----------|-------|
| [`examples/pilot_hostages.mp4`](examples/pilot_hostages.mp4) | 3 segments (anchor♀ → anchor♂ → Eden) | 29.1s | Hostages still in Gaza after 800 days |
| [`examples/ep02_victory.mp4`](examples/ep02_victory.mp4) | 5 segments (♀ → ♂ → ♀ → ♂ → Eden) | 30.6s | "We crushed Iran"… but did we? |

---

## 2. Deploy

### 2.1 Prerequisites
- Python 3.10+
- **FFmpeg** on `$PATH`
  - macOS: `brew install ffmpeg`
  - Linux (Debian/Ubuntu): `sudo apt install ffmpeg`
  - Windows: download from https://ffmpeg.org/download.html and add to PATH
- API keys:

| Service | Required for | Notes |
|---------|--------------|-------|
| **fal.ai** ([key](https://fal.ai/dashboard/keys)) | VEED Fabric 1.0 lip-sync (and Aurora fallback) | **Paid balance required** — the Free tier returns 403. Top up ~$10 on https://fal.ai/dashboard/billing |
| **ElevenLabs** ([key](https://elevenlabs.io/app/settings/api-keys)) | Hebrew TTS via `eleven_v3` + `language_code='he'` | **`eleven_v3` requires Creator plan or higher** ($22/mo). Free-tier accounts get 403 on this model |
| **Google AI Studio** ([key](https://aistudio.google.com/app/apikey)) | Nano Banana Pro image generation | **Optional** — only needed if you regenerate character images via `scripts/fix_v2.py`. The Streamlit UI uses pinned images from `examples/` and works without this key |

### 2.2 Install
```bash
git clone <this-private-repo>
cd mind-video
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # then edit .env and paste your three keys
```

### 2.3 Smoke test
```bash
python scripts/mini_test_lipsync.py
```
This generates one ~3-second clip end-to-end. If it produces an MP4, the deploy is healthy.

### 2.4 Reproduce the two shipped examples
```bash
python scripts/fix_v2.py pilot   # → output/pilot_v5/final.mp4 (≈29s)
python scripts/fix_v2.py ep02    # → output/ep02_v3/final.mp4 (≈31s)
```
Each script is **idempotent** — it skips any image/audio/video that already exists on disk, so re-runs after a partial failure resume cleanly.

**Cost per ~30s episode**: ~$3-5 (most of it is VEED Fabric at $0.08/s × 30s × 3-5 segments).

### 2.5 Local UI (recommended for non-CLI users)
```bash
streamlit run app.py
```
A browser tab opens at `http://localhost:8501` with an episode builder:
- 3 default segments pre-loaded (♀ anchor → ♂ anchor → Eden) with their pinned character images for visual consistency.
- Edit Hebrew text per segment (RTL textareas), add/remove segments, see a live cost estimate.
- Click **▶ Generate video** to watch real-time progress for each segment (image ✓ / audio ✓ / lip-sync ⟳ with elapsed seconds).
- When done, the final MP4 plays inline + a **⬇ Download** button. The output path is `output/<episode-name>/final.mp4`.
- Re-clicking Generate with the same episode name reuses cached steps — cheap iteration on a single line.

The UI uses the same shared functions in `src/pipeline/episode.py` as the CLI scripts, so anything you build there is reproducible from the command line.

---

## 3. The Channel 14 + Eden format

Every episode is a fixed three-beat structure:

```
[Channel 14 studio]   anchors deliver the regime line, dripping with adoration
       ↓
[Cut to living room]  Eden, with her stuffed bunny, asks one quiet question
       ↓
[Silence]             — there is no answer, because there is no answer
```

### Cast (pre-built)

| Character | Description | Voice | Tempo |
|-----------|-------------|-------|-------|
| **Female anchor** ([`examples/anchor_female_inlove.png`](examples/anchor_female_inlove.png)) | Mizrahi woman, 30s, dramatic eye makeup, gold hoops, tight black top with a giant **"14"**. Love-struck, swooning. | ElevenLabs **Laura** (`FGY2WhTYpPnrIDTdsKH5`), style 0.85 | 1.25× |
| **Male anchor** ([`examples/anchor_male_desk.png`](examples/anchor_male_desk.png)) | Mizrahi man, 30s, gelled hair, gold chain, dark polo with **"14"**. Cocky smirk, fist on desk. | ElevenLabs **Charlie** (`IKne3meq5aSn9XLyUdCD`), style 0.90 | 1.25× |
| **Eden** ([`examples/eden_puzzled.png`](examples/eden_puzzled.png)) | 7-10 y.o. Israeli girl, two braids with mismatched ties, pink pajamas, stuffed bunny. Puzzled, brow furrowed. | ElevenLabs **Jessica** (`cgSgspJ2msm6clMCkdW9`), style 0.25 | 1.0× |

All three are rendered in flat 2D **South Park style** (paper-cutout, thick outlines, bright flat colors) — the prompt fragment is shared across every image and pinned at the top of each script as `STYLE_SOUTHPARK`.

### Example script #1 — "Hostages" (`scripts/fix_episodes.py` → `fix_pilot`)

> **Female anchor** *(love-struck)*: "אני מאוהבת, איזה מנהיג חזק, איזה מנהיג דגול יש לנו, קרה לנו נס!"
>
> **Male anchor** *(fist-pumping)*: "לגמרי! לא משאירים אנשים מאחור, זה לא יקרה במשמרת שלנו!"
>
> **Eden** *(quiet, on the orange couch)*: "אמא, הוא אמר שלא משאירים אנשים מאחור, אבל את החטופים השארנו מאחור, השארנו שמונה מאות ימים. אמא, ארבעים ושישה מהם נרצחו במנהרות בעזה. אז למה הוא התכוון שלא משאירים אנשים מאחור? למה הוא התכוון אמא?"

Result: [`examples/pilot_hostages.mp4`](examples/pilot_hostages.mp4)

### Example script #2 — "Victory" (`scripts/fix_v2.py` → `fix_ep02`)

> **Female ♀**: "אני מאוהבת, איזה מנהיג חזק, איזה מנהיג דגול יש לנו, קרה לנו נס!"
>
> **Male ♂**: "לגמרי! באיראן השמדנו הכל! לא נשאר להם אפילו אורז למרק!"
>
> **Female ♀**: "ככה נראה ניצחון מוחלט! אין לנו יותר אויבים! איזה מנהיג!"
>
> **Male ♂**: "ממש! אפילו החמוצים בשמאל חייבים להודות! מנהיג ענק, חד פעמי, בן גוריון אבל פי אלף!"
>
> **Eden**: "אבל אמא, החמאס בעזה נשאר, לא? החיזבאללה ממשיכים עם הטילים וכל הצפון מופגז. אמא, ככה נראה ניצחון מוחלט? ככה נראה ביטחון? זה אנחנו ניצחנו אמא?"

Result: [`examples/ep02_victory.mp4`](examples/ep02_victory.mp4)

---

## 4. How it works — the orchestration

```
┌─────────────────────────────────────────────────────────────────────┐
│  Python script (e.g. scripts/fix_v2.py)                             │
│  • defines characters + per-line text + voice settings              │
│  • runs the four steps below, idempotently (skip-if-exists)         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────────┐
        ▼                      ▼                          ▼
┌──────────────────┐  ┌──────────────────┐    ┌─────────────────────┐
│ 1. IMAGES        │  │ 2. AUDIO         │    │  (per character     │
│ Nano Banana Pro  │  │ ElevenLabs v3    │    │   line, in parallel)│
│ (Google AI)      │  │ Hebrew TTS       │    │                     │
│ → output/.../    │  │ → raw .mp3       │    │                     │
│   *.png          │  │ → ffmpeg atempo  │    │                     │
│                  │  │   (e.g. 1.25×)   │    │                     │
└────────┬─────────┘  └────────┬─────────┘    └─────────────────────┘
         │                     │
         └──────────┬──────────┘
                    ▼
        ┌─────────────────────────────┐
        │ 3. LIP-SYNC VIDEO           │
        │ VEED Fabric 1.0 (fal.ai)    │
        │   primary @ $0.08/s, 480p   │
        │ Aurora (Creatify) fallback  │
        │   $0.10/s, +25% slower      │
        │ → segment_*.mp4             │
        └────────────┬────────────────┘
                     ▼
        ┌─────────────────────────────┐
        │ 4. CONCATENATE              │
        │ ffmpeg -f concat -c copy    │
        │ (re-encodes only on codec   │
        │  mismatch, libx264 + aac)   │
        │ → final.mp4 (9:16)          │
        └─────────────────────────────┘
```

**Key implementation details** (already battle-tested — see `lessons.md`):
- Each line gets its own MP4 — they're concatenated last so individual lines can be regenerated cheaply.
- VEED Fabric 1.0 was chosen after benchmarking 8 lip-sync providers on Hebrew (`scripts/compare_lipsync.py`); see `TASKS.md` for the full table.
- `tempo=1.25×` post-applied via `ffmpeg atempo` makes the anchors sound urgent/manic; Eden stays at 1.0 to keep her voice innocent.
- Polling pattern: `submit_async` → poll `status_async` every 8s → `result_async` → download MP4.

---

## 5. Advanced — Build your own

The pipeline is parameterized — you can keep the same plumbing and swap any of: theme, characters, voices, or the whole script.

### 5.1 New theme (same Channel 14 + Eden cast)
Easiest path. Copy `scripts/fix_v2.py` → `scripts/my_episode.py` and just edit:
- The Hebrew text inside each `generate_tts(text=..., voice_id=..., ...)` call.
- The `concat([...])` list (number/order of segments).

The character images (`anchor_female_*.png`, `anchor_male_desk.png`, `eden_puzzled.png`) are reusable — VEED Fabric only changes the lips per line, so the same still works for any text.

There are six more pilot scripts already drafted in [`briefs/emperors_clothes_pilot.md`](briefs/emperors_clothes_pilot.md) ("המשק פורח", "ניצחון מוחץ", "החטופים בראש סדר העדיפויות", "בחירות שוב", "חופש העיתונות", "יוקר הדיור") — pick one and wire it into a new script.

### 5.2 New characters
Replace the prompt block at the top of your script (search for `ANCHOR_IMAGES` in `scripts/pilot_v2.py` for the pattern). The recipe that produces consistent characters is:

```
"Generate a 9:16 image of <demographics>, <body/face features>, "
"<wardrobe + the channel-14 number}, "
"<expression — leaning forward / love-struck / fist on desk}, "
"<setting — anchor desk + screen behind / orange couch / etc.}, "
"Rendered in <STYLE_SOUTHPARK>."   # keep the style pinned
```

For a non-Channel-14 satirical theme, swap the wardrobe and the screen text. For a non-cartoon look, swap `STYLE_SOUTHPARK` (e.g. cartoonify, ghiblify, FLUX comic LoRA — see `CLAUDE.md` for the full table of stylized image models on fal.ai).

### 5.3 New voices

**Easy path — pick a stock ElevenLabs voice.**
The shipped cast uses three stock voices (Laura, Charlie, Jessica). Browse https://elevenlabs.io/voice-library, copy a voice ID, drop it into `voice_id="..."` in your script. Recommended starting settings:

| Use case | stability | similarity | style | tempo |
|----------|-----------|------------|-------|-------|
| Manic anchor | 0.20 | 0.75 | 0.85-0.90 | 1.25× |
| Calm child / narrator | 0.55 | 0.7 | 0.25 | 1.0× |
| Determined adult | 0.5 | 0.8 | 0.5 | 1.0-1.1× |

**Advanced path — clone a real voice.**
`scripts/clone_voices.py` does ElevenLabs Instant Voice Cloning (3 × ~90s YouTube clips → cloned voice ID). API key needs `Voices → Write` permission. Cloning is free (no TTS credits). **Ethics/ToS gotcha**: don't name the cloned voice after a public figure — ElevenLabs blocks those clones. Use a generic label like "Hebrew Narrator Male v3".

For Hebrew **emotion preservation** (e.g. record a human with the right delivery, then convert to a cloned voice), use Chatterbox S2S via `scripts/episode1_s2s.py` — it's language-agnostic. ElevenLabs STS does **not** work for Hebrew (passes audio through unchanged).

### 5.4 End-to-end stitch — a from-scratch script template

```python
# scripts/my_episode.py — adapt fix_v2.py
SEGMENTS = {
    "intro_anchor":  {"image": "...", "text": "...", "voice_id": "...", ...},
    "rebuttal":      {"image": "...", "text": "...", "voice_id": "...", ...},
    "eden_question": {"image": "...", "text": "...", "voice_id": "...", ...},
}

# In main():
await generate_image(prompt, image_path)        # for each unique image
await generate_tts(text, voice_id, audio_path)  # for each segment
await lipsync(image_path, audio_path, video_path)  # VEED Fabric 1.0
await concat([v1, v2, v3], final_path)          # ffmpeg
```

See `scripts/fix_v2.py` for a 220-line working reference of all four steps.

---

## 6. Repo layout

```
mind-video/
├── scripts/
│   ├── pilot_v2.py             # 3-segment pilot (anchor♀ → anchor♂ → Eden)
│   ├── fix_episodes.py         # Pilot v4 (hostages) + Ep02 v2 (victory)
│   ├── fix_v2.py               # Pilot v5 (puzzled Eden) + Ep02 v3 — LATEST
│   ├── generate_anchors.py     # Anchor design exploration (10 variants)
│   ├── generate_girl_v2.py     # Eden design exploration (5 variants)
│   ├── compare_lipsync.py      # 8-provider lip-sync benchmark
│   ├── clone_voices.py         # ElevenLabs IVC for new voices
│   └── episode1_s2s.py         # Chatterbox S2S (Hebrew voice conversion)
├── src/providers/              # Reusable provider classes (image/audio/video)
├── briefs/
│   └── emperors_clothes_pilot.md  # 6 ready-to-produce episode scripts
├── examples/                   # Two finished MP4s + character stills
├── output/                     # Generated artifacts (gitignored)
├── lessons.md                  # What works / what doesn't (read first)
├── TASKS.md                    # Living checkpoint of all production runs
├── CLAUDE.md                   # AI-assistant instructions
└── README.md                   # This file
```

---

## 7. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `403` from fal.ai | Out of balance → top up at https://fal.ai/dashboard/billing |
| `400` from ElevenLabs on `language_code='he'` | You're using `eleven_multilingual_v2` — switch to `eleven_v3` (only v3 supports `language_code`) |
| Anchors talk too slow / dead | Confirm `tempo=1.25` is being applied (ffmpeg `atempo` filter) — easy to miss on a re-run if file already exists |
| Video processing seems frozen | VEED Fabric ≈ 15s per second of audio. A 25s line takes ~4 min |
| Eden's mouth not synced well | Re-generate her image — the lip-sync model needs hands-not-near-face and a clearly visible mouth |
| Re-runs double-apply tempo (chipmunk audio) | Pipeline already guards against this via skip-if-exists — but if you blow away `_raw.mp3` keep both `_raw.mp3` and the final `.mp3`, and only atempo on freshly generated raw files |
| ElevenLabs blocks a voice clone | Don't name the clone after a public figure (ToS). Use a generic name |

For deeper troubleshooting, [`lessons.md`](lessons.md) catalogs every pitfall hit in production so far, and [`TASKS.md`](TASKS.md) is the running checkpoint of which model/version/iteration produced which output.
