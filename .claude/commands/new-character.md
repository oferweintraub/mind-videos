---
description: Generate 3 candidate stills for a new character, then promote one into the library
argument-hint: <description of the character> [style: south_park|lego|muppet|pixar|ghibli|comic|anime|<free text>]
---

The user wants to create a new character for the Mind Video pipeline.

User input: **$ARGUMENTS**

Walk them through this conversational flow. Do not skip steps; ask before each step that requires user judgment (image pick, voice). All commands run from the repo root.

## Step 1 — Plan

From the user's input, decide:
- A short **slug** (lowercase, underscores, ≤ 25 chars). e.g. `young_woman_lego`, `news_anchor_male`. Prefer descriptive over generic.
- A **style** label. If the user named one explicitly, use it. Otherwise pick from: `south_park`, `lego`, `muppet`, `pixar`, `ghibli`, `comic`, `anime`, or write a free-text style phrase.
  - **If the user is undecided between styles, offer multi-style generation:** pass a comma-separated list (e.g. `lego,south_park,muppet`) — `character_lab.py` will produce one candidate per style and `option_<N>_style.txt` next to each `option_<N>.png` records which style is which.
- A **description** — one sentence describing the character (demographics, hair, clothing, expression, props). If the user's input is sparse, expand it — but show your expansion to the user and let them edit before generating.

Briefly summarize your slug + style + description back to the user and ask: "Generate candidates with these settings? (y/n or edit)"

## Step 2 — Generate candidates

Run (from repo root):

```bash
# Single-style: 3 variations
python scripts/character_lab.py \
  --slug <slug> \
  --style <style> \
  --description "<description>" \
  --count 3

# Multi-style: one candidate per style (use when undecided)
python scripts/character_lab.py \
  --slug <slug> \
  --style lego,south_park,muppet \
  --description "<description>"
```

This calls Nano Banana Pro in parallel. Takes ~60-90s. Each candidate costs ~$0.04. Requires `GOOGLE_API_KEY` in `.env`.

If the script fails with a missing key error, tell the user and stop.

## Step 3 — Show the candidates

The 3 candidates are at:

- `characters/_candidates/<slug>/option_1.png`
- `characters/_candidates/<slug>/option_2.png`
- `characters/_candidates/<slug>/option_3.png`

Tell the user the paths so they can open them. In Claude Cowork, attach/display them using the standard image-display mechanism if available; otherwise just list the paths. Then ask: **"Which one do you want to keep? (1, 2, or 3 — or 'regenerate' to try again with tweaks)"**

Selection criteria to mention:
- Face clarity, hair clearly defined, eyes well-lit
- **Mouth fully visible and clean** (this is what gets lip-synced — covered mouths break the video)
- No hands near the face
- Expression matches the intended use

## Step 4 — Pick a voice

The full voice catalog lives in [`config/voices.yaml`](../../config/voices.yaml). Show it to the user with:

```bash
python scripts/list_voices.py
# or filter:
python scripts/list_voices.py --good-for old_man
```

Quick suggestions to mention inline (no need to look up the file for these):

| Voice | ID | Best for |
|-------|-----|----------|
| Laura | `FGY2WhTYpPnrIDTdsKH5` | Bright, dramatic adult female |
| Charlie | `IKne3meq5aSn9XLyUdCD` | Energetic adult male |
| Jessica | `cgSgspJ2msm6clMCkdW9` | Calm, child-like |
| Brian | `nPczCjzI2devNBz1zQrb` | Deep, mature American male — old man / narrator |
| George | `JBFqnCBsd6RMkjVDRZzb` | Warm British grandfather |
| Bill | `pqHfZKP75CvOlQylNhV4` | Gravelly older male — grumpy grandpa |

Ask: "Voice ID? (use one above, run `python scripts/list_voices.py` to see all 10 stock voices, or paste an ID from elevenlabs.io/voice-library.)"

Also ask (with sensible defaults shown):
- Tempo? (1.0 = natural, 1.25 = manic/urgent — anchors use 1.25, narrators use 1.0, weary/sad use 0.95)
- Display name? (e.g. "Female Anchor (Channel 14)" — defaults to titlecased slug)

## Step 5 — Promote the chosen candidate

Run:

```bash
python scripts/save_character.py \
  --slug <slug> \
  --pick <N> \
  --display-name "<display_name>" \
  --description "<description>" \
  --style <style> \
  --voice-id <voice_id> \
  --voice-name "<voice_name>" \
  --tempo <tempo>
```

This copies `option_<N>.png` to `characters/<slug>/image.png` and writes `characters/<slug>/manifest.json`.

## Step 6 — Confirm

Verify both files exist (use `ls characters/<slug>/`). Tell the user:

> Character `<slug>` saved. You can now reference it in scripts as:
>
> ```
> ## <slug>
> <Hebrew text here>
> ```
>
> Try it: `/new-script` to draft an episode that uses this character, or `/make-video` to render an existing one.
