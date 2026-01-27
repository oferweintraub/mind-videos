# Mind Video - Hebrew Democracy Video Pipeline

Automated pipeline for generating 1-minute Hebrew educational videos with AI-generated images, voice synthesis, and lip-sync video generation.

## Quick Start

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy and fill in API keys
cp .env.example .env

# Run full workflow
python scripts/proper_workflow.py all
```

## API Keys Required

Create a `.env` file with:

```bash
FAL_KEY=               # fal.ai - Video generation (VEED Fabric)
ELEVENLABS_API_KEY=    # ElevenLabs - Hebrew TTS
GOOGLE_API_KEY=        # Google AI - Image generation (Nano Banana Pro)
```

## The 6-Step Workflow

```
Step 1: Generate 3 reference images → Select best one
Step 2: Use reference to generate 5 scene images → Select best 3
Step 3: Prepare text (45-60s) → Split into 3 segments
Step 4: Generate audio with ElevenLabs (serious → urgent → angry)
Step 5: Generate lip-sync videos with VEED Fabric
Step 6: Concatenate with FFmpeg (direct cuts)
```

## Scripts

### `scripts/proper_workflow.py` - Main Workflow
Full video generation from scratch.

```bash
# Run all steps
python scripts/proper_workflow.py all

# Run step by step
python scripts/proper_workflow.py 1  # Generate 3 ref images
python scripts/proper_workflow.py 2  # Generate 5 scenes with ref
python scripts/proper_workflow.py 3  # Prepare text segments
python scripts/proper_workflow.py 4  # Generate audio
python scripts/proper_workflow.py 5  # Generate videos
python scripts/proper_workflow.py 6  # Concatenate
```

### `scripts/regenerate_videos.py` - Asset Reuse
Generate new videos with different characters while reusing existing audio.

```bash
# New character, reuse existing audio
python scripts/regenerate_videos.py \
    --character ashkenazi \
    --audio-dir output/previous_run \
    --output-dir output/new_video

# New character AND new voice
python scripts/regenerate_videos.py \
    --character "Israeli man, age 40, short dark hair, beard" \
    --voice daniel \
    --output-dir output/male_video
```

**Character presets:** `ashkenazi`, `sephardic`, `ethiopian`, `russian`, `israeli_man`

**Voice presets:** `jessica` (female), `daniel` (male), `george` (male), `brian` (male)

### `scripts/mini_test_lipsync.py` - Quick Test
Test fal.ai connectivity and lip-sync with minimal audio.

```bash
python scripts/mini_test_lipsync.py
```

## Tech Stack

| Component | Provider | API |
|-----------|----------|-----|
| Images | Nano Banana Pro | Google AI |
| Audio/TTS | ElevenLabs V3 | ElevenLabs |
| Video + Lip-sync | VEED Fabric 1.0 | fal.ai |
| Concatenation | FFmpeg | Local |

## Cost Estimate (per video)

| Step | Cost |
|------|------|
| Images (8 total) | ~$0.08 |
| Audio (~55s) | ~$0.30 |
| Video (~55s @ 720p) | ~$4.00 |
| **Total** | **~$4.40** |

## Project Structure

```
mind-video/
├── scripts/
│   ├── proper_workflow.py      # Main 6-step workflow
│   ├── regenerate_videos.py    # Asset reuse workflow
│   └── mini_test_lipsync.py    # Quick testing
├── src/
│   ├── providers/
│   │   ├── audio/elevenlabs.py # Hebrew TTS
│   │   ├── image/nano_banana.py # Image generation
│   │   └── video/fal/veed_fabric.py # Lip-sync video
│   └── utils/
│       ├── ffmpeg.py           # Video operations
│       └── video_transitions.py
├── config/default.yaml         # Configuration
├── docs/
│   ├── PRD.md                  # Product requirements
│   └── tasks.md                # Implementation tracking
└── output/                     # Generated assets
```

## Troubleshooting

**fal.ai 403 error?**
- Balance exhausted. Top up at https://fal.ai/dashboard/billing

**Face not consistent?**
- Ensure reference image is passed to EVERY scene generation
- Check that reference has clear, well-lit face

**Lip-sync issues?**
- Avoid images with hands near face
- Try different emotion preset (slower speech = better sync)

**Audio stuttering?**
- Regenerate the audio segment with `scripts/regenerate_videos.py --step 4`

## Documentation

- `docs/PRD.md` - Full product requirements and workflow details
- `docs/tasks.md` - Implementation status and task tracking
- `CLAUDE.md` - AI assistant instructions
