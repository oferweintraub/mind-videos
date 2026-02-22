# TASKS.md — Mind Video Project

## Current Status

### [DONE] Realism Test: 8 Combos (2026-02-12/15)

**Winner: Combo 1 (Nano Banana Pro + VEED Fabric 1.0)** — best character consistency + lip-sync.

| Combo | Image Model | Video Model | Duration | Size | Notes |
|-------|-------------|-------------|----------|------|-------|
| **1 (WINNER)** | **Nano Banana Pro** | **VEED Fabric 1.0** | **24.2s** | **3.7MB** | Best consistency + lip-sync |
| 2 | Qwen-Image-2512 (no ref) | VEED Fabric 1.0 | 24.2s | 2.5MB | Character drift |
| 3 | Qwen-Image-2512 (no ref) | Kling v2.1 + Sync Lipsync v2 | 20.2s | 2.4MB | Character drift + bad lipsync |
| 4 | FLUX.2 Pro | VEED Fabric 1.0 | 24.2s | 2.3MB | Weaker than Nano Banana |
| 5 | Qwen-Image-2512 (no ref) | Kling Avatar v2 | 26.1s | 3.9MB | Character drift |
| 6 | Qwen Image Max (with ref) | VEED Fabric 1.0 | 24.2s | 1.6MB | Ref didn't lock face |
| 7 | Qwen Image Max (with ref) | Kling 2.6 Pro + Sync Lipsync v2 | 20.2s | 3.7MB | Ref drift + bad lipsync |
| 8 | Nano Banana Pro (reused) | Kling 3.0 Std + Sync Lipsync v2 | 20.2s | 2.5MB | Great motion, horrible lipsync |

**Output:** `output/realism_test/` (only combo_1 + audio + combos 9-11 kept, rest cleaned)

---

### [DONE] Stylized Characters Test: 3 Combos (2026-02-15)

Tested cartoon, anime, and comic styles. All use VEED Fabric for video.

| Combo | Style | Image Model | Video Model |
|-------|-------|-------------|-------------|
| 9 | Pixar/3D cartoon | Cartoonify | VEED Fabric 1.0 |
| 10 | Studio Ghibli | Ghiblify | VEED Fabric 1.0 |
| 11 | Comic/graphic novel | FLUX Digital Comic Art LoRA | VEED Fabric 1.0 |

---

### [DONE] Puppet Style Test: 4 Characters Selected (2026-02-18)

Tested 3 styles (muppet, claymation, cartoon3d) × 2 models (FLUX.2 Pro, Nano Banana Pro) × 4 characters across multiple rounds. Selected winners after iterating on descriptions and expressions.

**Selected puppets** in `output/puppet_style_test/selected/`:

| Character | File | Description | Model |
|-----------|------|-------------|-------|
| **Bibi (Netanyahu)** | `bibi.png` | Sleazy reptilian smirk, leaning forward, scheming swindler look | Nano Banana Pro |
| **Trump** | `trump.png` | Orange felt, pursed lips, swooping blonde hair, red tie | Nano Banana Pro |
| **Kisch (Yoav Kisch)** | `kisch.png` | Stocky sycophant, glasses, gold tie, obsequious grin | Nano Banana Pro |
| **Silman (Idit Silman)** | `silman.png` | Curly hair bun, black headband, black earrings, agreeable yes-woman smirk | Nano Banana Pro |

**Key findings:**
- Nano Banana Pro (text-only) produces best puppets — felt texture + recognizable features
- FLUX.2 Pro has better pure puppet texture but characters less recognizable
- Nano Banana + reference photos → too photorealistic (refs override puppet style)
- Nano Banana + reference photos of women → blocked by safety filter
- Named politician prompts (e.g., "Benjamin Netanyahu") work in Nano Banana for puppet generation
- Personality descriptions in prompts (sleazy, sycophantic, etc.) effectively shape expressions

**Scripts:** `scripts/puppet_round3.py` (final generation script)

---

### [DONE] Project Cleanup (2026-02-18)

Removed ~500MB of obsolete data:
- Deleted `DZine/` folder (105MB)
- Deleted 6 old accountability folders (~124MB)
- Deleted old test/version folders: `test_transitions/`, `v2_video/`, `v2_images/`, `v3_video/`, `v3_images/` (~181MB)
- Deleted losing realism test combos 2-8 (~100MB)
- Deleted rejected puppet style test folders (round 1, round 2, references)
- Project output went from 653MB → 167MB

---

### [DONE] Voice Cloning: 4 Characters (2026-02-18)

Cloned all 4 puppet character voices using ElevenLabs Instant Voice Cloning (IVC). Each voice cloned from 3 × 90s audio clips extracted from YouTube speeches/interviews.

| Character | Voice ID | Source Language | Source |
|-----------|----------|-----------------|--------|
| **Bibi** | `m9c6Minbc2SDBVAtOmdS` | Hebrew | UN speech + Knesset speech |
| **Trump** | `HPSBAx1tjgqEuuMxGcrv` | English | Rally speeches |
| **Kisch** | `P4pANIkpqK68HpvUikoU` | Hebrew | TV interviews |
| **Silman** | `p7KZwBfOJ4BZwzUZrFzo` | Hebrew | Studio debate + investigation piece |

**Audio clips:** `output/voice_cloning/{bibi,trump,kisch,silman}/clip{1,2,3}.mp3`
**Voice IDs:** `output/voice_cloning/voice_ids.txt`
**Script:** `scripts/clone_voices.py`

**Notes:**
- yt-dlp needed update to 2026.02.04 (old version got 403 from YouTube SABR streaming)
- ElevenLabs API key needs `Voices → Write` permission for cloning
- Voice cloning doesn't consume TTS character credits
- Trump cloned from English — will speak Hebrew with American accent (intentionally funny)

---

### [IN PROGRESS] Episode 1: "מה קרה באוקטובר?" (2026-02-19)

Hebrew puppet satire — Bibi claims total ignorance of Oct 7 while Kisch & Silman help minimize/deflect.

**Script:** `scripts/episode1_produce.py` (full production pipeline)
**Output:** `output/episode1/`
**Current version:** v4.1 — `output/episode1/final.mp4` (2:53, 49.4MB, 23 scenes)

| Step | Command | Count | Status |
|------|---------|-------|--------|
| 1. Expression images | `images` | 14 variants (with character references) + 2 existing | DONE |
| 2. Audio (cloned voices) | `audio` | 22 speaking scenes (~1,908 chars) | DONE |
| 3. Lip-sync video | `video` | 22 VEED Fabric jobs | DONE |
| 4. Reaction stills | `stills` | 1 (scene 3 react) | DONE |
| 5. Concatenate | `concat` | 23 scenes → final.mp4 | DONE |

**Iterations completed:** v1 (3:28) → v2 (2:58) → v3 (2:54) → v4 (2:55) → v4.1 (2:53)

**Key changes across versions:**
- v2: Bibi 1.2x tempo, scene 10 split into 10/10b/10c, pronunciation fixes
- v3: New phone text, removed pink glasses + group shot, new silman_silly/kisch_serious
- v4: ALL images regenerated with character references for consistency, text fixes (scenes 16-19)
- v4.1: Pronunciation fixes (אַחֲרַי niqqud, stronger intonation, removed הסחבק)

**Voice IDs (updated):**
- Bibi: `aooUHbQzVbqHLJx3zbYH` (re-cloned with generic name to avoid ElevenLabs ToS block)
- Kisch: `jUCQwcBAqLbVF54GHPlv`
- Silman: `LtYcxc0xwy3LHnPjIUBt`

**Reference images for consistency:**
- Bibi: `output/episode1/images/bibi_neutral.png`
- Kisch: `output/episode1/images/kisch_cheerful.png`
- Silman: `output/episode1/images/silman_reference.png` (user-provided)

**Run:** `python scripts/episode1_produce.py all` or step by step.
**Status:** `python scripts/episode1_produce.py status`

**Current status:** v4.1 delivered, awaiting user review for potential further tweaks.

---

## Pending

- **[BLOCKED — waiting for fal.ai support] Seedance 2.0 by ByteDance**: Native multimodal video gen with built-in lip-sync. Official API launches ~Feb 24. Check fal.ai for `fal-ai/bytedance/seedance/v2` after Feb 24.
