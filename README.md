# Mind Video — Hebrew satirical video pipeline

Turn a few lines of Hebrew dialogue into a finished 9:16 video where animated characters speak with lip-synced mouths. Driven from inside Claude Desktop with three slash commands. **No coding required.**

```
/new-character   → design a new character (candidate images, pick one)
/new-script      → draft Hebrew dialogue across N characters
/make-video      → render the script into a finished MP4
```

> 📌 **Important:** these are *Claude-Code slash commands*, not regular shell commands.
> They run inside a Claude Desktop **Code-tab session that has this folder open** (covered in Step 6 below).
> They will not work from a regular Terminal window.

Two finished examples in [`examples/`](examples/) — both produced from this exact pipeline:

| File | Format | Duration |
|------|--------|----------|
| [`pilot_hostages.mp4`](examples/pilot_hostages.mp4) | 3 segments (♀ anchor → ♂ anchor → Eden) | 29.1s |
| [`ep02_victory.mp4`](examples/ep02_victory.mp4) | 5 segments | 30.6s |

---

## What you'll need

A one-time setup of about **30 minutes**. After that, each new video is 5–15 minutes of clicking and ~$1–3 in API credits.

| Need | Where to get it | Cost |
|------|-----------------|------|
| Mac or Windows computer | – | – |
| Claude Desktop | [claude.com/download](https://claude.com/download) | Free download (Pro plan recommended) |
| Three API keys | see [Step 3](#step-3--get-your-three-api-keys) | ~$30 to start |
| Three command-line tools (`git`, `python`, `ffmpeg`) | see [Step 2](#step-2--install-the-prerequisites) | Free |

---

## Step 1 — Install Claude Desktop

1. Go to **[https://claude.com/download](https://claude.com/download)** in your browser.
2. Click **Download for macOS** (or Windows).
3. Open the downloaded file. On Mac, drag Claude into your Applications folder.
4. Launch Claude. Sign in with your Anthropic account (Pro plan recommended).

Once it opens you'll see tabs at the top: **Chat**, **Cowork**, **Code**. We'll use the **Code** tab for everything below.

---

## Step 2 — Install the prerequisites

You need three command-line tools. Open the **Terminal** app (press <kbd>⌘ Space</kbd>, type "Terminal", hit <kbd>Enter</kbd>).

### macOS

If you've never used Homebrew, install it first by pasting this into Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then install the three tools:

```bash
brew install git python@3.12 ffmpeg
```

### Windows

Install each from its official page:
- **Git** — [git-scm.com/download/win](https://git-scm.com/download/win)
- **Python 3.12** — [python.org/downloads](https://www.python.org/downloads/) (during install, check **"Add Python to PATH"**)
- **FFmpeg** — [ffmpeg.org/download.html](https://ffmpeg.org/download.html) → unzip → add the `bin/` folder to your PATH

### Verify it worked

Paste this into Terminal:

```bash
git --version && python3 --version && ffmpeg -version | head -1
```

You should see three version numbers. If one errors, that one didn't install correctly — fix it before continuing.

---

## Step 3 — Get your three API keys

Each service has a free signup. You only pay for usage.

| Service | What it does | Where to get a key | What it costs |
|---------|--------------|--------------------|---------------|
| **fal.ai** | Lip-syncs your character to the audio | [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys) | Add ~$10 to balance — pay per second of video |
| **ElevenLabs** | Reads Hebrew text aloud in a chosen voice | [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys) | **Creator plan required ($22/month)** — Free/Starter return errors on Hebrew |
| **Google AI** | Generates the still images of your characters | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | Free tier is fine to start |

For each: sign up → find the **API keys** section → click **Create key** → copy the long string. Save them in a temporary note — you'll paste them into a config file in Step 5.

> ⚠️ **ElevenLabs tier matters**: Free and Starter plans don't support Hebrew on the `eleven_v3` model the pipeline uses. Upgrade to **Creator** ($22/mo) before you start, or you'll get a 400 error on every TTS call.

---

## Step 4 — Download the project

In Terminal:

```bash
cd ~/Documents
git clone https://github.com/oferweintraub/mind-videos.git mind-video
cd mind-video
```

If you'd rather not use git, you can download a ZIP from the repo's web page → unzip → put the folder at `~/Documents/mind-video/`.

Then install the Python dependencies (one-time):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

This downloads ~200 MB of Python libraries. Takes 1–2 minutes.

---

## Step 5 — Add your API keys to the project

Still in Terminal, in the `mind-video` folder:

```bash
cp .env.example .env
open -e .env
```

This opens the `.env` file in TextEdit. You'll see:

```
FAL_KEY=
ELEVENLABS_API_KEY=
GOOGLE_API_KEY=
```

Paste each key after the `=` sign. No quotes, no spaces. Save and close.

---

## Step 6 — Open the project in Claude Desktop

1. Open Claude Desktop.
2. Click the **Code** tab.
3. At the top of the input area, click the **Project folder** dropdown → **Open folder**.
4. Navigate to `~/Documents/mind-video/` and choose it.

Claude will read the project. You'll know it worked because typing `/` in the input shows `/new-character`, `/new-script`, and `/make-video` in the command list.

> 💡 **Permission tip for non-coders**: in Claude's settings (or per-session), set the permission mode to **"Accept edits"**. Claude will auto-accept file edits but still ask before running shell commands — a safe default.

---

## Step 7 — Render the example to confirm everything works

In the Claude chat input, type:

```
/make-video example_hostages
```

This renders the example episode that ships with the repo (3 segments, ~30 seconds, ~$1.50 in credits). Claude will:

1. Estimate the cost and ask **"proceed?"** — say **yes**.
2. Run the pipeline (TTS → lip-sync → concat). About 3–4 minutes wallclock.
3. Tell you the path to the finished MP4 and open it for you.

If the video plays — congratulations, the entire pipeline is working. You're ready to make your own.

---

## The three slash commands

### `/new-character`

Design a new character. Type a description (and optionally a style):

```
/new-character a young woman with curly red hair, freckles, denim jacket, in lego style
```

Claude will:
1. Pick a slug + style + description and ask you to confirm.
2. Generate **3 candidate images** with Nano Banana Pro (~60 seconds, ~$0.12 total).
3. Show you the three images at `characters/_candidates/<slug>/option_{1,2,3}.png` and ask which to keep.
4. Ask which **voice** you want (suggests Laura, Charlie, Jessica from ElevenLabs stock — paste any voice ID from [elevenlabs.io/voice-library](https://elevenlabs.io/voice-library)).
5. Save the chosen image + voice settings into your character library.

After this, the character is reusable in any future script.

**Built-in styles** (just type the name): `south_park`, `lego`, `muppet`, `pixar`, `ghibli`, `comic`, `anime`. Anything else is treated as a free-text style description.

For higher-fidelity styles (e.g. true Muppet felt textures via FLUX LoRA training), see [`docs/advanced-styles.md`](docs/advanced-styles.md).

### `/new-script`

Draft a Hebrew dialogue script. Two ways to use it:

**From a topic:**

```
/new-script grandma_remembers a satirical piece about a politician forgetting his promises
```

**From an existing draft** (`.txt`, `.md`, `.docx`, or `.pdf`):

```
/new-script my_draft --from ~/Documents/dialogue.docx
```

Claude will:
1. List your available characters and ask who should appear and in what order.
2. Draft 3–5 Hebrew segments matching each character's personality (or, in draft-import mode, map segments from your file to characters).
3. Show you the draft and ask for revisions.
4. Save it to `episodes/<slug>/script.md`.
5. Validate that every character referenced exists in your library.

### `/make-video`

Render a script into a finished MP4:

```
/make-video grandma_remembers
```

Claude will:
1. Estimate the cost (~$0.10 per second of audio).
2. Ask you to confirm.
3. Run the pipeline:
   - **TTS** per segment (ElevenLabs, ~5–15s each)
   - **Lip-sync** per segment (VEED Fabric 1.0, ~15s of wallclock per second of finished video)
   - **Concat** into one 9:16 MP4 (FFmpeg)
4. Show the path to `episodes/<slug>/final.mp4` and open it.

The pipeline is **idempotent** — if a step fails or you tweak one line in the script, re-running only regenerates what changed. Iterating on a single line is cheap.

---

## What videos cost

| Action | Cost |
|--------|------|
| Designing one new character (3 candidates) | ~$0.12 |
| One 30-second video (3 segments) | ~$1.50 – $3 |
| One 60-second video (5–6 segments) | ~$3 – $6 |
| ElevenLabs Creator plan (monthly fixed) | $22/month |

Most of the per-video cost is lip-sync ($0.08/second of finished video). TTS comes from your ElevenLabs monthly quota. Image generation is pennies.

---

## The script format (in case you want to edit by hand)

`episodes/<slug>/script.md` looks like this:

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

Rules:
- Each `## ` heading starts a new segment.
- The first word after `##` **must** be a character slug from `characters/`.
- Anything else on the heading line is a note for humans (ignored by the pipeline).
- The same character can appear multiple times — each `##` is a separate segment with its own audio + video.
- Hebrew text goes between headings. Multiple lines are fine.

---

## Stuck?

| Symptom | What's wrong | Fix |
|---------|--------------|-----|
| `/new-character` etc. don't appear when you type `/` | Claude isn't reading the project folder | Re-open the folder via the **Project folder** dropdown in Claude Desktop |
| `403` from fal.ai | Out of balance | Top up at [fal.ai/dashboard/billing](https://fal.ai/dashboard/billing) |
| `400` from ElevenLabs about `language_code='he'` | You're on Free or Starter | Upgrade to **Creator** ($22/mo) |
| `ffmpeg atempo failed` | FFmpeg install is broken | Run `brew reinstall ffmpeg` (Mac) |
| Pipeline seems frozen | Lip-sync is slow by design — about 15s of wallclock per second of finished video. A 25s line takes ~4 minutes | Wait |
| Character looks different in each segment | The candidate image you picked doesn't have a strong, distinctive face | Re-run `/new-character` and pick a clearer one |
| Mouth not lip-syncing well | The image has hands near the face, or mouth is partially covered | Re-pick a candidate with a clean, fully-visible mouth |
| ElevenLabs blocks a voice clone | Don't name the clone after a public figure (against their ToS) | Use a generic name like "Hebrew Narrator Male" |

If something else breaks, [`lessons.md`](lessons.md) catalogs every pitfall hit during production.

---

## Sharing it with friends (no install needed for them)

If you have collaborators who want to render videos but don't want to install anything, the project ships with a browser-based UI ([`app.py`](app.py)) you can deploy for free on **Streamlit Community Cloud**:

1. Push the repo to your own GitHub.
2. Sign in at [share.streamlit.io](https://share.streamlit.io) with GitHub.
3. **New app** → pick the repo, branch `master`, main file `app.py`.
4. **Advanced settings → Secrets** → paste:
   ```toml
   APP_PASSWORD = "<pick a shared password>"
   ```
5. **Deploy**. First boot takes ~3 minutes.
6. Share the URL + password.

Collaborators see a password screen, then a sidebar where they paste their **own** API keys (they spend their own credits, not yours). Limits: 1 GB RAM, ephemeral filesystem (download MP4s immediately), the app sleeps after ~7 days of inactivity.

You can also run the same app locally without deploying:

```bash
source venv/bin/activate
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## How it works (under the hood)

```
┌──────────────────────────────────────────────┐
│  scripts/make_episode.py <slug>              │
│  • parse episodes/<slug>/script.md           │
│  • for each segment, run steps 1–3           │
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
            │ → final.mp4 (9:16)         │
            └────────────────────────────┘
```

VEED Fabric 1.0 was chosen as the lip-sync provider after benchmarking 8 providers on Hebrew audio (script: [`scripts/compare_lipsync.py`](scripts/compare_lipsync.py)). Implementation notes and every gotcha hit in production live in [`lessons.md`](lessons.md).

### Repo layout

```
mind-video/
├── characters/                  # Your character library — one folder per character
│   ├── anchor_female/
│   │   ├── manifest.json        # voice + metadata
│   │   └── image.png            # the still used for lip-sync
│   ├── anchor_male/  eden/
│   └── _candidates/             # work area for /new-character (gitignored)
├── episodes/                    # Your scripts + their outputs
│   ├── example_hostages/
│   │   ├── script.md            # input (you write this)
│   │   ├── audio/  videos/      # intermediates (gitignored)
│   │   └── final.mp4            # output
│   └── <your-episode>/
├── scripts/                     # CLI tooling (slash commands wrap these)
│   ├── character_lab.py         # generate N candidate stills
│   ├── save_character.py        # promote candidate → library
│   ├── make_episode.py          # render script.md → final.mp4
│   └── ...
├── src/                         # Python modules
│   ├── character.py             # Character/Voice loader
│   ├── script_format.py         # script.md parser
│   └── pipeline/episode.py      # TTS / lip-sync / concat
├── .claude/commands/            # The three slash commands
│   ├── new-character.md
│   ├── new-script.md
│   └── make-video.md
├── examples/                    # Two finished example MP4s
├── app.py                       # Streamlit UI
├── docs/advanced-styles.md      # FLUX LoRA / Cartoonify / Ghiblify routes
├── lessons.md   TASKS.md        # Working notes
└── README.md
```

For developers extending the pipeline, see [`docs/advanced-styles.md`](docs/advanced-styles.md), [`lessons.md`](lessons.md), and [`TASKS.md`](TASKS.md).
