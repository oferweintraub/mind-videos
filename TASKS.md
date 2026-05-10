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
**Current version:** v4.3 — `output/episode1/final.mp4` (2:49, 48.0MB, 23 scenes)

| Step | Command | Count | Status |
|------|---------|-------|--------|
| 1. Expression images | `images` | 14 variants (with character references) + 2 existing | DONE |
| 2. Audio (cloned voices) | `audio` | 22 speaking scenes (~1,908 chars) | DONE |
| 3. Lip-sync video | `video` | 22 VEED Fabric jobs | DONE |
| 4. Reaction stills | `stills` | 1 (scene 3 react) | DONE |
| 5. Concatenate | `concat` | 23 scenes → final.mp4 | DONE |

**Iterations completed:** v1 (3:28) → v2 (2:58) → v3 (2:54) → v4 (2:55) → v4.1 (2:53) → v4.2 (2:53) → v4.3 (2:49)

**Key changes across versions:**
- v2: Bibi 1.2x tempo, scene 10 split into 10/10b/10c, pronunciation fixes
- v3: New phone text, removed pink glasses + group shot, new silman_silly/kisch_serious
- v4: ALL images regenerated with character references for consistency, text fixes (scenes 16-19)
- v4.1: Pronunciation fixes (אַחֲרַי niqqud, stronger intonation, removed הסחבק)
- v4.2: Full niqqud for "בדש" phrase (didn't help enough)
- v4.3: Replaced "בדש" line entirely → "למה לא העירו אותי? תגידו, זה משהו שינון יכול להריץ עליו איזה קונספירציה ונגמור עם זה?"

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

**Current status:** v4.3 delivered (ElevenLabs TTS). Next step: re-record all 22 lines as human recordings → convert via Chatterbox S2S → regenerate videos for v5 with better pronunciation/emotion.

**S2S pipeline ready:** `scripts/episode1_s2s.py`
- `list` — shows all 22 lines to record with status
- `convert` — converts recordings in `output/episode1/recordings/` via Chatterbox S2S
- Uses `fal-ai/chatterbox/speech-to-speech` with clip2 reference per character
- After convert: `python scripts/episode1_produce.py video && python scripts/episode1_produce.py concat`

---

### [DONE] Lip-Sync Provider Comparison (2026-02-23)

Benchmarked 8 fal.ai lip-sync providers against Hebrew audio to find a cheaper or better alternative to VEED Fabric 1.0. Tested on both photorealistic images (20.6s) and puppet Bibi (11.4s short + 25.4s long Hebrew monologue).

**Round 1:** VEED Fabric vs LatentSync (photorealistic)
**Round 2:** + Kling Avatar v2 Std, Sync Lipsync 1.9, MuseTalk (photorealistic)
**Round 3:** VEED Fabric vs Kling Avatar v2 Std vs Kling Avatar v2 Pro (photorealistic)
**Round 4:** VEED vs Kling Std on puppet Bibi (11.4s)
**Round 5:** + OmniHuman v1.5, Aurora (Creatify) on puppet Bibi (11.4s)
**Round 6:** VEED vs Aurora vs OmniHuman on puppet Bibi long sentence (25.4s) — **final showdown**

| Provider | Model ID | $/sec | Quality | Speed | Verdict |
|----------|----------|-------|---------|-------|---------|
| **VEED Fabric 480p** | `veed/fabric-1.0` | **$0.08** | Crisp, sharp | **~100s** | **WINNER — best balance** |
| Aurora (Creatify) | `fal-ai/creatify/aurora` | $0.10 | Good + hand movements | ~210s | **Backup option** |
| Kling Avatar v2 Std | `fal-ai/kling-video/ai-avatar/v2/standard` | $0.056 | Human nuances, less sharp | ~300s | Interesting but slower |
| Kling Avatar v2 Pro | `fal-ai/kling-video/ai-avatar/v2/pro` | $0.115 | Small bump over Std | ~500s | Not worth 2x cost |
| OmniHuman v1.5 | `fal-ai/bytedance/omnihuman/v1.5` | $0.16 | Nice micro-expressions | Unreliable | Timed out on 25s clip |
| Sync Lipsync 1.9 | `fal-ai/sync-lipsync` | $0.012/s | Poor | ~218s | Not viable |
| MuseTalk | `fal-ai/musetalk` | Free | Poor | ~376s | Not viable |
| LatentSync | `fal-ai/latentsync` | $0.20 flat | Unusable | ~356s | Rejected |

**Also investigated (not tested):**
- Kling O1 — no audio/lip-sync support, video gen only
- Google Veo 3.1 — text-to-video only, can't feed existing audio+image

**Final verdict:** VEED Fabric 1.0 confirmed as the best choice. Aurora is a quality backup if VEED has issues. No provider change needed — cost optimization should focus on content (shorter segments, fewer segments) not provider switching.

**Script:** `scripts/compare_lipsync.py`
**Output:** `output/lipsync_comparison/` (photorealistic, puppet_bibi, puppet_bibi_long)

---

### [DONE] S2S Investigation: Chatterbox Wins (2026-02-19)

Tested 3 speech-to-speech providers for Hebrew voice conversion:

| Provider | Model | Hebrew Support | Result |
|----------|-------|---------------|--------|
| **Chatterbox (fal.ai)** | `fal-ai/chatterbox/speech-to-speech` | **Yes (language-agnostic)** | **WINNER — best voice conversion quality** |
| ElevenLabs STS | `eleven_multilingual_sts_v2` | No | Passes audio through unchanged for Hebrew |
| Resemble AI S2S | `POST /synthesize` with `<resemble:convert>` | Yes | Works but lower quality than Chatterbox |

**Key finding:** Chatterbox is language-agnostic (converts voice timbre, preserves delivery/pronunciation). ElevenLabs STS does NOT support Hebrew — outputs identical audio regardless of settings. Resemble AI works but voice creation via API requires Business plan ($$$).

**Script:** `scripts/episode1_s2s.py` (ready to use)
**Test outputs:** `output/episode1/test_chatterbox_clip{1,2,3}.wav`, `test_resemble_harel.mp3`

---

### [DONE] Streamlit UI + Streamlit Cloud deploy config (2026-04-28)

`app.py` for local episode generation with 3-character pinned cast (Channel 14 anchors + Eden). Added password gate (`APP_PASSWORD` via `st.secrets`) and bring-your-own-keys sidebar so collaborators can use a hosted instance without exposing the owner's fal.ai/ElevenLabs balance. `packages.txt` provisions `ffmpeg` on the build host. README §2.6 documents the deploy.

---

### [DONE] Reorg into Character Library + Slash Commands (2026-05-05 → 2026-05-06)

Restructured the project so anyone with permission can clone it and produce videos end-to-end via Claude Code or Claude Cowork — no Python knowledge required. Three slash commands now drive the full workflow:

- `/new-character "<desc>" [style]` — generate N candidates → pick → save to `characters/<slug>/`
- `/new-script <slug> [topic | --from <draft>]` — draft Hebrew dialogue, optionally importing `.txt`/`.md`/`.docx`/`.pdf`
- `/make-video <slug>` — render `episodes/<slug>/script.md` → `final.mp4`

**New layout**:
- `characters/<slug>/{manifest.json, image.png}` — manifest-driven library
- `episodes/<slug>/{script.md, audio/, videos/, final.mp4}` — per-episode self-contained
- `src/character.py` + `src/script_format.py` — Character/Voice dataclasses + Markdown script parser
- `scripts/{character_lab, save_character, make_episode, extract_text, list_voices}.py` — CLI tooling
- `.claude/commands/{new-character, new-script, make-video}.md` — slash command instructions
- `config/voices.yaml` — curated ElevenLabs voice catalog (with `--good-for` filter via `list_voices.py`)
- `docs/advanced-styles.md` — FLUX LoRA / Cartoonify / Ghiblify routes for stronger style fidelity
- `scripts/_archive/` — historical one-off scripts (20 files, kept for reference)

**Character lab supports multi-style** (`--style lego,south_park,muppet`) when the user is undecided — produces one candidate per style. **`make_episode.py` accepts both positional slug and `--episode` flag** for scriptability, plus prints audio-duration-aware ETAs during lip-sync.

**Validated end-to-end**: ran `make_episode.py example_hostages` against real APIs — produced `episodes/example_hostages/final.mp4` (4.2 MB, 480×864, 20.6s) for ~$1.50 in fal.ai cost. **Cowork test confirmed working** — user created a new character (`red_haired_woman`) and rendered a new episode (`red_woman_intro`) entirely through the slash command flow.

**Commits**: `8f8af19` (reorg), `ce196e0` (draft import), `86a42c5` (README), `202c328` (Cowork-test polish: voice catalog, multi-style, ETA, `--episode` flag).

**`app.py` refactored** to load characters from disk (no more hardcoded cast). It still defaults to Channel-14 + Eden if those slugs exist, but works generically for any cast in `characters/`.

---

### [DONE] Streamlit Wizard — Cast → Script → Render (2026-05-06)

Replaced the form-y `app.py` with a guided 3-step wizard for non-developers. Live at https://mind-video-play.streamlit.app/ behind `APP_PASSWORD = "yallasanity_2026"`. Charcoal + warm-gold theme, Inter UI / Source Serif headers, hidden Streamlit chrome, custom step indicator.

**Modules** (commit `3aed7ee`):
- `src/wizard/state.py` — session state, project export/import .zip
- `src/wizard/theme.py` — palette, CSS, step indicator, status pills
- `src/wizard/step1_cast.py` — character builder (description + style + N candidates → pick → voice)
- `src/wizard/step2_script.py` — segment builder (avatar + character dropdown + RTL Hebrew textarea + reorder)
- `src/wizard/step3_render.py` — preflight + live progress + result screen
- `app.py` — shell, gate, sidebar, step routing
- `config/voice_previews/` — 10 pre-generated Hebrew preview MP3s (~512 KB total)

**Settings drawer**: API keys (BYO), project export/import .zip (works around Streamlit Cloud's ephemeral disk), reset.

---

### [DONE] Phase 1: Edit + Reference image + Robust errors (2026-05-08)

Three independent UX improvements:

1. **Edit existing characters** (`e4e90cb`): Edit button on each cast tile. Change voice/tempo/display name. Optional "🎨 Regenerate images" sub-flow → pick from new candidates → Apply.

2. **Reference image upload** (`6819143`): Optional file picker. When provided, routes through FLUX Kontext Pro (`fal-ai/flux-pro/kontext`) instead of Nano Banana Pro — purpose-built for "this same person, but in style X" prompts. Avoids Google's safety filter on photo refs of women + caricature.

3. **Centralized friendly errors** (`c50bc96`): New `src/wizard/errors.py` translates ElevenLabs/fal.ai/Google/ffmpeg/network failures into actionable Markdown. Used across step1/step3.

Plus security fix (`624706d`): per-session API key isolation. The wizard's settings drawer no longer writes user keys to `os.environ` (process-global on Streamlit Cloud). New `src/wizard/creds.py` reads keys from `st.session_state` only. Pipeline functions take explicit `*, fal_key=`, `elevenlabs_api_key=`, `google_api_key=` kwargs. fal_client uses `AsyncClient(key=...)` per call.

---

### [DONE] Phase 2: Cloud state + share links (Supabase) (2026-05-10)

Cloud-backed projects so users can close the tab and resume later, or share a project URL with collaborators (with optional API key handoff).

**Supabase setup** (`1165bf6`): One-time SQL setup file (`supabase/setup.sql`) — paste into the Supabase SQL Editor, click Run. Creates `public.projects` table + `character-images` storage bucket. RLS deliberately off — security via unguessable 12-char project IDs (~72 bits entropy). Run via Playwright/claude-in-chrome.

**Persistence module** (`edb2ec4`): `src/wizard/persistence.py` with `is_configured()`, `new_project_id()`, `create_project / load_project / save_state / delete_project`, `upload/download_character_image`, `serialize_cast / deserialize_cast`, `sync_cast_images_to_storage / hydrate_cast_images_from_storage`. State helpers `ensure_project_id()` and `auto_save()` wired into every mutator.

**Share-link UI + URL gate bypass** (`0822786`): Settings sidebar shows project URL + "Include my API keys in the link" toggle (default off). When the URL has `?p=<id>` and the project exists, the password gate is skipped — same trust model as Excalidraw share links.

**Phase 2.6-2.9** (`32ed371`): Step-timing fix (`go_to(N)` everywhere instead of direct `st.session_state.step = N`), edit-existing now persists immediately via `add_character`, delete-project button (DELETE-to-confirm), Recent projects sidebar list (session-scoped, capped at 8).

**Live**: secrets configured on Streamlit Cloud (`SUPABASE_URL`, `SUPABASE_KEY`). Round-trip verified: demo loads → URL updates to `?p=<id>` → fresh session opens same URL → state hydrates → no password needed.

---

## Pending

- **Record 22 lines for S2S conversion**: Record all speaking lines with correct Hebrew pronunciation and emotion → save to `output/episode1/recordings/` → run `python scripts/episode1_s2s.py convert` → regenerate videos for v5
- **[BLOCKED — waiting for fal.ai support] Seedance 2.0 by ByteDance**: Native multimodal video gen with built-in lip-sync. Official API launches ~Feb 24. Check fal.ai for `fal-ai/bytedance/seedance/v2` after Feb 24.

## Backlog (nice-to-have, not committed)

- **Commit `red_haired_woman` + `red_woman_intro` as a second shipped example?** They're untracked test artifacts from the Cowork test. If the result is good, they'd serve as a non-Channel-14 demo for new users. If throwaway, `rm -rf` them.
- **End-to-end render test on the deployed wizard** — we've never actually clicked Generate on the Supabase-backed deploy. Pipeline itself is unchanged so should work, but worth a confirmation run (~$1.50).
- **localStorage-backed recent projects** — currently session-only. Persisting across full browser restarts requires `streamlit-local-storage` or a small JS injection.
- **Phase 3 direction (when ready)** — see end-of-session notes: polish/robustness vs. more creator features (voice cloning, multi-language, music) vs. productize (analytics, custom domain, pricing) vs. wait-for-tester-feedback. Recommend the last until 2-3 testers actually use it.
