# Mind Video - Hebrew Democracy Video Pipeline

## Project Overview

Automated pipeline for generating 1-minute Hebrew educational videos promoting democracy, accountability, empathy, and diverse perspectives.

## Tech Stack

| Component | Provider | API |
|-----------|----------|-----|
| Images | Nano Banana Pro | Google AI |
| Audio/TTS | ElevenLabs V3 | ElevenLabs (he) |
| Video + Lip-sync | VEED Fabric 1.0 | Fal.ai |
| Concatenation | FFmpeg | Local |

## Project Structure

```
scripts/
├── proper_workflow.py      # THE main workflow (use this)
├── regenerate_videos.py    # Asset reuse (new character, same audio)
└── mini_test_lipsync.py    # Quick test for debugging

src/
├── providers/
│   ├── audio/elevenlabs.py   # Hebrew TTS
│   ├── image/nano_banana.py  # Image generation with reference
│   └── video/fal/veed_fabric.py  # Lip-sync video
├── utils/
│   ├── ffmpeg.py             # Video operations
│   └── video_transitions.py  # Concatenation
└── ...

config/default.yaml  # Configuration
briefs/              # Content briefs
```

## Quick Start

```bash
# Run the full workflow
source venv/bin/activate
python scripts/proper_workflow.py all

# Or step by step:
python scripts/proper_workflow.py 1  # Generate 3 ref images → select best
python scripts/proper_workflow.py 2  # Generate 5 scenes with ref → select 3
python scripts/proper_workflow.py 3  # Prepare text segments
python scripts/proper_workflow.py 4  # Generate audio (ElevenLabs)
python scripts/proper_workflow.py 5  # Generate videos (Fabric 1.0)
python scripts/proper_workflow.py 6  # Concatenate with FFmpeg

# Quick lip-sync test
python scripts/mini_test_lipsync.py
```

---

## THE PROPER WORKFLOW (MUST FOLLOW EXACTLY)

### Step 1: Generate Reference Images
- Generate **3 potential reference images** with Nano Banana Pro
- Select **best one** based on: face clarity, hair definition, lip-sync friendliness
- Save as `selected_reference.png`

### Step 2: Generate Scene Images WITH Reference
- Use selected reference to generate **5 scene images** at various home settings
- **CRITICAL**: Pass reference image to EVERY generation call
- Ensure face, lighting, character consistent across all 5
- Select **best 3** for the 3 video segments

### Step 3: Prepare Text
- Get full text for 45-60 second video
- Split into **3 parts** matching emotional arc

### Step 4: Generate Audio
- Use **ElevenLabs Jessica voice** (`EXAVITQu4vr4xnSDxMaL`)
- Emotions: `serious` → `urgent` → `angry`

### Step 5: Generate Videos
- Use **Fabric 1.0** (`veed/fabric-1.0`) via fal.ai
- Input: segment image + segment audio
- **Note**: ~15 seconds processing per second of audio

### Step 6: Concatenate
- **FFmpeg with direct cuts** (no crossfades, no gaps)

---

## Image Generation with Reference

**CRITICAL: Always pass reference image to maintain face consistency.**

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=api_key)
reference_bytes = Path("selected_reference.png").read_bytes()

response = client.models.generate_content(
    model="nano-banana-pro-preview",
    contents=[
        types.Part.from_bytes(data=reference_bytes, mime_type='image/png'),
        "Generate a 9:16 image of this SAME woman in a living room...",
    ],
    config=types.GenerateContentConfig(response_modalities=['image', 'text'])
)
```

**Prompt tips:**
- "this SAME woman (use the reference image)"
- "Maintain EXACT same face, hair, features"
- "No hands near face" (for lip-sync)

**Selection criteria:**
| Criteria | Weight |
|----------|--------|
| Face match | HIGH |
| Hair consistency | HIGH |
| Clear mouth (lip-sync) | HIGH |
| Expression match | MEDIUM |

---

## Audio Emotion Presets

| Preset | Use Case |
|--------|----------|
| `serious` | Calm setup, storytelling |
| `urgent` | Building tension |
| `angry` | Peak intensity, call to action |
| `determined` | Strong conclusion |

---

## API Keys Required

```bash
# .env file
FAL_KEY=               # Video generation (fal.ai)
ELEVENLABS_API_KEY=    # Hebrew TTS
GOOGLE_API_KEY=        # Image generation
```

---

## Troubleshooting

**Video generation slow?**
- Longer audio = longer processing (~15s per second of audio)
- Use 480p resolution for faster processing

**Face not consistent?**
- Ensure reference image is passed to EVERY scene generation
- Check that reference has clear, well-lit face

**Lip-sync issues?**
- Avoid images with hands near face
- Use cleaner face shots
- Try different emotion preset (slower speech = better sync)

**fal.ai errors?**
- Check balance: https://fal.ai/dashboard/billing
- 403 = exhausted balance, need to top up
