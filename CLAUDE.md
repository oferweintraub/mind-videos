# Mind Video - Hebrew Democracy Video Pipeline

## Project Overview

Automated pipeline for generating 1-minute Hebrew educational videos promoting democracy, accountability, empathy, and diverse perspectives. Uses AI for script generation, image creation, voice synthesis, and video production.

## Tech Stack

| Component | Provider | Primary API | Fallback |
|-----------|----------|-------------|----------|
| LLM | Claude 4.5 Sonnet | Anthropic | Gemini 3.0 Flash |
| Images | Nano Banana Pro | Google AI (Imagen 3) | - |
| Audio/TTS | ElevenLabs V2 | ElevenLabs | - |
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
└── utils/               # FFMPEG, metadata tracking
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
