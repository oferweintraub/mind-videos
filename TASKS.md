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

**Key findings:**
- Nano Banana Pro has strongest reference image adherence (face-locks across scenes)
- VEED Fabric's one-step pipeline (image+audio→video) produces far better lip-sync than 2-step (motion→lipsync overlay)
- Kling 3.0 has better motion quality but the 2-step lipsync approach fundamentally fights the motion
- Qwen Image Max `/edit` endpoint does NOT truly lock face identity — treats reference as style guide

**Output:** `output/realism_test/`

**Files:** `scripts/realism_test.py` (combos 1-11), `scripts/kokoro_tts.js`

---

### [DONE] Stylized Characters Test: 3 Combos (2026-02-15)

Tested cartoon, anime, and comic styles. All use VEED Fabric for video (confirmed works with stylized input).

| Combo | Style | Image Model | Video Model | Duration | Size | Notes |
|-------|-------|-------------|-------------|----------|------|-------|
| 9 | Pixar/3D cartoon | Cartoonify (Combo 1 photos) | VEED Fabric 1.0 | 24.2s | 2.2MB | Subtle 3D effect, close to photorealistic |
| 10 | Studio Ghibli | Ghiblify (Combo 1 photos) | VEED Fabric 1.0 | 24.2s | 2.7MB | Beautiful anime aesthetic, distinctive |
| 11 | Comic/graphic novel | FLUX Digital Comic Art LoRA | VEED Fabric 1.0 | 24.2s | 2.4MB | Bold ink outlines, no ref support (character differs) |

**Key findings:**
- VEED Fabric handles all stylized inputs perfectly — preserves art style while animating
- Cartoonify and Ghiblify transform existing photos, so character consistency is inherited from source
- FLUX Comic Art LoRA is text-only (no reference images), so character drifts between scenes
- All stylized combos were fast (~3-5 min each) and cheap
- Ghibli style is the most visually distinctive

**Image Models Researched (all on fal.ai):**

| Style | Model | fal.ai ID | Price | Ref Support |
|-------|-------|-----------|-------|-------------|
| Puppet/Muppet | Train FLUX LoRA | `fal-ai/flux-lora-fast-training` | $2 train + $0.035/MP | Yes (via LoRA) |
| Comic/Graphic Novel | FLUX Digital Comic Art | `fal-ai/flux-2-lora-gallery/digital-comic-art` | $0.021/MP | No (trigger: `d1g1t4l`) |
| Cartoon (Pixar) | Cartoonify | `fal-ai/cartoonify` | $0.10/img | Photo→cartoon |
| Cartoon (Ghibli) | Ghiblify | `fal-ai/ghiblify` | $0.05/img | Photo→cartoon |
| Any + consistency | FLUX Kontext Pro | `fal-ai/flux-pro/kontext` | $0.04/img | Yes (89% consistency) |
| Character consistency | Instant Character | `fal-ai/instant-character` | $0.10/MP | Built-in |

**Other lip-sync options on fal.ai:** SadTalker (`fal-ai/sadtalker` — anime), MuseTalk (`fal-ai/musetalk` — $0.04/inference)

---

## Pending

- Review stylized videos (combos 9-11) and select preferred styles
- Consider puppet style via FLUX LoRA training ($2) if puppet look is desired
- Consider FLUX Kontext Pro for comic style with character consistency
- **[BLOCKED — waiting for fal.ai support] Seedance 2.0 by ByteDance**: Native multimodal video gen with built-in lip-sync. Official API launches ~Feb 24. Anti-deepfake filters on real faces won't affect stylized characters. Check fal.ai for `fal-ai/bytedance/seedance/v2` after Feb 24.
