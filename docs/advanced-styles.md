# Advanced styles — beyond Nano Banana Pro

The default character pipeline (`scripts/character_lab.py` → Nano Banana Pro) renders any style label by feeding a style description into a single prompt. This works well for South Park, comic, and most cartoon variants, but for **highly specific looks** (Lego, Muppet, Pixar 3D) the result can drift between candidates.

This doc covers the alternative paths through the **fal.ai stylized image stack** that produce more authentic results, at the cost of more setup. All of them produce stills that VEED Fabric 1.0 lip-syncs the same way — the rest of the pipeline (TTS → lip-sync → concat) doesn't change.

---

## When to choose each path

| You want | Use | Setup cost | Per-image cost |
|----------|-----|------------|----------------|
| Quick experimentation, any style | Nano Banana Pro (default) | None | ~$0.04 |
| Authentic Muppet / felt puppet look, **consistent across many images** | FLUX LoRA training (`fal-ai/flux-lora-fast-training`) | $2 one-time training, ~10 min | ~$0.04/image |
| Pixar 3D look from a real photo | Cartoonify (`fal-ai/cartoonify`) | None — pass an input photo | ~$0.05 |
| Studio Ghibli watercolor anime | Ghiblify (`fal-ai/ghiblify`) | None | ~$0.05 |
| Comic book art | FLUX Digital Comic LoRA gallery | None | ~$0.04 |
| Same character across 50+ images, any style | FLUX Kontext Pro (`fal-ai/flux-pro/kontext`) | None — pass reference image | ~$0.05 |
| Brand-new character from one reference photo | Instant Character (`fal-ai/instant-character`) | None | ~$0.04 |

---

## 1. FLUX LoRA training (custom puppet/Muppet style)

**Best for**: 5+ episodes featuring the same Muppet-style character. The training data teaches the model what **felt puppet anatomy** looks like (oversized head, fuzzy texture, ping-pong eyes, fabric mouth) far better than a text prompt can.

**Setup** (one-time, ~10 min, $2):

1. Collect 8-15 reference images of the puppet style you want. Pinterest / a Muppet wiki works.
2. Zip them.
3. Run via the fal.ai dashboard or API:

```python
import fal_client
result = fal_client.subscribe(
    "fal-ai/flux-lora-fast-training",
    arguments={
        "images_data_url": "<your zip URL>",
        "trigger_word": "muppet_style",  # picks something distinctive
        "is_style": True,
    },
)
print(result["diffusers_lora_file"]["url"])  # save this
```

4. Save the resulting LoRA URL.

**Use** (per character):

```python
result = fal_client.subscribe(
    "fal-ai/flux-lora",
    arguments={
        "prompt": "muppet_style portrait of a journalist puppet, news desk, ...",
        "loras": [{"path": "<your saved URL>", "scale": 1.0}],
        "image_size": "portrait_16_9",
    },
)
```

Saves to `characters/_candidates/<slug>/option_*.png` exactly like `character_lab.py` does — you can promote with `scripts/save_character.py` unchanged.

---

## 2. Cartoonify (Pixar 3D from a photo)

**Best for**: turning a real photo into a Pixar-3D character. Excellent face fidelity if you have a clear input photo.

```python
result = fal_client.subscribe(
    "fal-ai/cartoonify",
    arguments={"image_url": "<photo URL>"},
)
# result["image"]["url"] -> save to characters/<slug>/image.png
```

Pair it with a stable ElevenLabs voice and you have a one-shot photo→character pipeline.

---

## 3. Ghiblify (Studio Ghibli watercolor anime)

Same shape as Cartoonify but with the Ghibli aesthetic:

```python
result = fal_client.subscribe(
    "fal-ai/ghiblify",
    arguments={"image_url": "<photo URL>"},
)
```

Works particularly well for younger characters and outdoor scenes.

---

## 4. FLUX Kontext Pro (consistency across many shots)

**Best for**: keeping the same character recognizable across dozens of images. Pass a reference image; FLUX Kontext respects identity better than prompt-only generation.

```python
result = fal_client.subscribe(
    "fal-ai/flux-pro/kontext",
    arguments={
        "image_url": "<reference image URL>",
        "prompt": "this same character, now seated at a kitchen table holding a mug, ...",
        "image_size": "portrait_16_9",
    },
)
```

If you find Nano Banana Pro drifts between scenes (face slightly different in candidate 1 vs 2), Kontext is the upgrade.

---

## 5. Instant Character (one-shot character creation from a photo)

**Best for**: you have a photo of a real person (or a hand-drawn sketch) and want a stylized character that looks like them.

```python
result = fal_client.subscribe(
    "fal-ai/instant-character",
    arguments={
        "image_url": "<photo URL>",
        "prompt": "stylized 3D cartoon character, ...",
    },
)
```

---

## Wiring it into the existing pipeline

The character library doesn't care **how** the image was generated — only that there's an `image.png` in the character's directory and a `manifest.json` next to it. So the integration is always:

1. Generate candidates by whatever route (LoRA / Cartoonify / Ghiblify / etc.).
2. Save them to `characters/_candidates/<slug>/option_<N>.png` (mirroring `character_lab.py`'s output layout).
3. Use `scripts/save_character.py --slug <slug> --pick <N> ...` to promote one.

If you want to add a new route as a first-class slash command (e.g. `/new-puppet`), copy `scripts/character_lab.py` and swap the fal.ai endpoint, then add a sibling `.claude/commands/new-puppet.md`.

---

## Why these aren't on the default path

The default flow uses Nano Banana Pro for three reasons:

1. **No training step** — you can iterate from idea to candidate in 60 seconds.
2. **Single API key** — `GOOGLE_API_KEY` is enough; fal.ai is only used for lip-sync.
3. **Style flexibility from prompts** — one model handles every style label, even ones it's never seen, by reading the description.

The trade-off is **cross-image consistency**. If you only need 3-5 images of a character (one per episode), Nano Banana Pro is fine. If you need 30 images for a longer series, the LoRA + Kontext path pays for itself.
