# Mind Video - Hebrew Democracy Video Pipeline

## Project Overview

Automated pipeline for generating 1-minute Hebrew educational videos promoting democracy, accountability, empathy, and diverse perspectives. Uses AI for script generation, image creation, voice synthesis, and video production.

## Tech Stack

| Component | Provider | Primary API | Fallback |
|-----------|----------|-------------|----------|
| LLM | Claude 4.5 Sonnet | Anthropic | Gemini 3.0 Flash |
| Images | Nano Banana Pro | Google AI (Imagen 3) | - |
| Audio/TTS | ElevenLabs V3 | ElevenLabs (he) | - |
| Video (Workflow 1) | VEED Fabric | Fal.ai | Replicate |
| Video (Workflow 2) | Kling 2.5 + Sync | Fal.ai | Replicate |

## Project Structure

```
src/
├── main.py              # CLI entry point
├── config.py            # Configuration management
├── schemas/             # Pydantic models
│   ├── brief.py         # ContentBrief for detailed script steering
│   ├── script.py        # Script and ScriptRequest models
│   ├── segment.py       # Video segment definitions
│   └── validation.py    # Quality validation schemas
├── providers/           # External API integrations
│   ├── base.py          # Base classes, circuit breaker, batch handling
│   ├── llm/             # Claude, Gemini
│   ├── audio/           # ElevenLabs
│   ├── image/           # Nano Banana (Google AI)
│   └── video/           # VEED Fabric, Kling, Sync (fal/ and replicate/)
├── services/            # Business logic
│   ├── script_generator.py
│   ├── scene_planner.py
│   ├── quality_validator.py
│   └── subtitle_generator.py
├── pipeline/            # Orchestration
│   ├── workflow1.py     # Image-based (~$4.50)
│   └── workflow2.py     # Video-based (~$6.00)
└── utils/               # FFMPEG, transitions, metadata
    ├── ffmpeg.py        # Core FFmpeg operations
    ├── video_transitions.py  # Sequential transitions (no speech overlap)
    ├── audio_utils.py   # Audio preprocessing for lip-sync
    ├── image_utils.py   # Mosaic splitting, image manipulation
    └── metadata.py      # Cost and metadata tracking
```

## Key Commands

```bash
# Run single segment test
python -m src.main test --text "שלום עולם" --image ./ref.png

# Generate full video (simple mode)
python -m src.main generate --topic "government accountability" --angle "empathetic"

# Generate full video (detailed brief mode - recommended)
python -m src.main generate --brief ./briefs/october7_investigation.yaml --image ./ref.png

# Check configuration
python -m src.main status

# Health check all providers
python -m src.main health
```

## Two Workflows

**Workflow 1 (Image-based, ~$4.50)**
- Uses VEED Fabric for direct image+audio → video with lip-sync
- Faster, cheaper, good for most use cases

**Workflow 2 (Video-based, ~$6.00)**
- Uses Kling for image → video with motion
- Then Sync for adding lip-sync
- Higher quality motion, better for dynamic content

## Image Generation Strategy

To avoid Nano Banana rate limits and improve character consistency:

**Mosaic Approach**
1. Generate a 2x3 mosaic with 6 character variations in one API call
2. Split into 6 individual images using PIL (no API calls)
3. User selects best 3 images
4. Apply reuse pattern `[1, 1, 2, 2, 3]` across 5 segments

**Variations in Mosaic:**
- Sofa, kitchen, balcony, standing, close-up, side angle
- Same character, different settings/poses

**Benefits:**
- 1 API call instead of 5-8
- Better character consistency
- User control over image selection
- Cost: ~$0.02 vs ~$0.10

## Content Briefs

For quality output, use detailed briefs instead of simple topic/angle:

```yaml
# briefs/example.yaml
title: "כותרת בעברית"
key_points:
  - "נקודה ראשונה"
  - "נקודה שנייה"
emotional_tone: "determined"  # angry, hopeful, cynical, etc.
rhetorical_devices:
  - "rhetorical_questions"
  - "contrast"
call_to_action: "מה הצופה צריך לעשות"
```

## Important Conventions

### Hebrew Text
- All scripts generated in Hebrew
- RTL encoding handled in subtitle generator
- ~15 characters/second speech pace estimate

### Error Handling
- Circuit breaker pattern: providers auto-disable after 5 failures
- Batch operations return `BatchResult` with structured error tracking
- Per-operation timeouts (video: 300s, polling: 600s)

### Provider Fallback
- Fal.ai is primary for all video operations
- Replicate is automatic fallback on failure
- `FallbackProvider` wrapper handles switching

## API Keys Required

```bash
# .env file
FAL_API_KEY=           # Primary video provider
REPLICATE_API_TOKEN=   # Fallback video provider
ELEVENLABS_API_KEY=    # Hebrew TTS
ANTHROPIC_API_KEY=     # Claude LLM
GOOGLE_API_KEY=        # Gemini LLM + Imagen
```

## Cost Tracking

Costs are tracked per operation in `output/<project>/metadata.yaml`:
- ElevenLabs: ~$0.30/min of audio
- VEED Fabric: ~$0.08/sec of video
- Kling: ~$0.07/sec of video
- Sync: ~$0.05/sec of video

## Video Transitions (Critical Guidelines)

### The Problem with Overlapping Transitions
Traditional video crossfades (xfade) **overlap content from both segments**. This causes speech from segment 1 and segment 2 to play simultaneously, which sounds terrible for talking-head videos.

### Solution: Sequential Transitions
**Always use sequential transitions** for videos with speech:

1. Segment 1 plays **completely** (ALL speech finishes)
2. Video fades to black (short visual fade ~0.15s)
3. Black screen with silence (gap of 0.3-0.5s)
4. Video fades in from black
5. Segment 2 plays **completely**

**Key principle: Speech must NEVER overlap. Let each segment's audio finish completely before transitioning.**

### Configuration (`config/default.yaml`)
```yaml
transitions:
  audio_crossfade: false  # MUST be false for speech videos
  audio_gap: 0.5          # Silence gap between segments (seconds)
  audio_fade_duration: 0.15  # Video fade duration (keep short)
```

### Implementation Details
- Use `concatenate_with_smart_transitions()` for multiple segments
- `detect_scene_changes_by_image()` identifies same-scene cuts (same image reused)
- Same-scene cuts can use shorter gaps (0.3s)
- Scene changes use longer gaps (0.5s)

### What NOT to Do
- **Don't use `audio_crossfade: true`** - causes speech overlap
- **Don't fade audio** - it cuts off speech before it finishes
- **Don't use xfade offset** that overlaps actual content

### Testing Transitions
```bash
# Run transition tests
python tests/test_crossfade_transitions.py

# Test files output to: output/test_transitions/
```

### Duration Impact
- Old overlap mode: `total = sum(durations) - transitions` (shorter)
- Sequential mode: `total = sum(durations) + gaps` (longer, but correct)

## Testing

```bash
# Syntax check
python3 -m py_compile src/**/*.py

# Unit tests (requires API keys)
pytest tests/
```

## Common Tasks

### Adding a New Provider
1. Create class inheriting from `BaseProvider` (or specific base)
2. Implement `health_check()` and main methods
3. Add `_handle_api_error()` for error conversion
4. Register in `providers/__init__.py`

### Creating a New Brief
1. Copy `briefs/example_template.md` or `.yaml`
2. Fill in key_points (most important)
3. Set emotional_tone and rhetorical_devices
4. Run with `--brief ./briefs/your_brief.yaml`

### Debugging Failed Segments
1. Check `output/<project>/metadata.yaml` for error details
2. Look at `segment_XX_*.mp4` files for partial outputs
3. Circuit breaker state in provider logs
