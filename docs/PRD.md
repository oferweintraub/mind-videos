# Hebrew Democracy Video Pipeline - PRD

## Mission
Generate automated 1-minute Hebrew educational videos promoting democracy, accountability, empathy, and diverse perspectives.

---

## Tech Stack

| Component | Tool | Primary API | Fallback |
|-----------|------|-------------|----------|
| **Images** | Nano Banana Pro | Google AI | - |
| **LLM** | Claude Sonnet 4.5 | Anthropic | Gemini 3.0 |
| **Audio** | ElevenLabs V2 | ElevenLabs Direct | - |
| **Image→Video+Lipsync** | VEED Fabric 1.0 | **Fal.ai** | Replicate |
| **Image→Video** | Kling 2.5 Pro | **Fal.ai** | Replicate |
| **Video→Video+Lipsync** | sync/lipsync-2-pro | **Fal.ai** | Replicate |
| **Concatenation** | FFMPEG | Local | - |
| **Data Validation** | Instructor + Pydantic | Local | - |

---

## Two Workflows

### Workflow 1: Image-Based (~$3.50/video)
```
Input: Topic + Guidelines + Reference Image
                ↓
    Claude: Write script → 3 options (A/B test)
                ↓
    Claude: Select best → Break into 6-8 segments
                ↓
    Claude: Define scenes (camera, lighting, expression per segment)
                ↓
    Nano Banana Pro (Google): Generate character images (6-8 settings)
                ↓
    ElevenLabs: Generate Hebrew audio per segment
                ↓
    VEED Fabric 1.0 (Fal.ai): Image + Audio → Video with lip-sync
                ↓
    Claude: Validate quality (remake if needed)
                ↓
    FFMPEG: Add subtitles + Concatenate clips
                ↓
Output: 1-minute video + thumbnails + metadata
```

### Workflow 2: Video-Based (~$5-6/video)
```
Same as Workflow 1 until audio generation, then:
                ↓
    Kling 2.5 Pro (Fal.ai): Image + motion prompt → Video (no audio)
                ↓
    sync/lipsync-2-pro (Fal.ai): Video + Audio → Video with lip-sync
                ↓
    Continue with validation, subtitles, concatenation
```

---

## Input/Output

**Input:**
- Topic (e.g., "government accountability")
- Angle/Guidelines (e.g., "empathetic, solution-focused")
- Reference image (optional)

**Output:**
- `./output/{topic}_{timestamp}/`
  - `video.mp4` (45-75 seconds)
  - `subtitles.srt` (Hebrew, RTL)
  - `thumbnails/` (2 best frames)
  - `metadata.yaml` (A/B tracking)

---

## Key Features

| Feature | Description |
|---------|-------------|
| **A/B Testing** | 3 script options, LLM-as-judge or human selection |
| **Fast Preview** | 3-4 segments (~$1.50) for direction validation |
| **Quality Validation** | LLM checks each segment, can order remake |
| **Hebrew Subtitles** | Customizable font, size, color, background |
| **Drop-in Providers** | Swap models via config (Claude ↔ Gemini) |
| **Error Handling** | 2-3 retries, then alert user |
| **Schema Validation** | Instructor + Pydantic for all LLM outputs |

---

## Cost Breakdown (Workflow 1)

| Step | Tool | Cost (Fal.ai) |
|------|------|---------------|
| Images (6-8) | Nano Banana Pro | ~$0.10 |
| Script + Validation | Claude API | ~$0.10 |
| Audio (60s) | ElevenLabs | ~$0.30 |
| Video (50s @ 480p) | VEED Fabric | ~$4.00 ($0.08/sec) |
| Video (50s @ 720p) | VEED Fabric | ~$7.50 ($0.15/sec) |
| Subtitles | FFMPEG | FREE |
| **Total (480p)** | | **~$4.50** |
| **Total (720p)** | | **~$8.00** |

**Recommendation**: Use 480p for previews/drafts, 720p for final output.

---

## Project Structure

```
mind-video/
├── src/
│   ├── main.py                    # CLI entry point
│   ├── config.py                  # Settings & API keys
│   ├── schemas/                   # Pydantic models (Instructor)
│   │   ├── script.py
│   │   ├── segment.py
│   │   ├── scene.py
│   │   └── validation.py
│   ├── pipeline/
│   │   ├── orchestrator.py        # Main coordinator
│   │   ├── workflow1.py           # Image-based
│   │   └── workflow2.py           # Video-based
│   ├── providers/
│   │   ├── base.py                # Abstract interfaces
│   │   ├── llm/
│   │   │   ├── claude.py          # Default
│   │   │   └── gemini.py          # Drop-in alternative
│   │   ├── image/
│   │   │   └── nano_banana.py     # Google AI
│   │   ├── audio/
│   │   │   └── elevenlabs.py
│   │   └── video/
│   │       ├── base_video.py      # Abstract video interface
│   │       ├── fal/               # Primary (Fal.ai)
│   │       │   ├── veed_fabric.py
│   │       │   ├── kling.py
│   │       │   └── sync_lipsync.py
│   │       └── replicate/         # Fallback
│   │           ├── veed_fabric.py
│   │           ├── kling.py
│   │           └── sync_lipsync.py
│   ├── services/
│   │   ├── script_generator.py
│   │   ├── scene_planner.py
│   │   ├── quality_validator.py
│   │   └── subtitle_generator.py
│   └── utils/
│       ├── ffmpeg.py
│       └── metadata.py
├── docs/
│   ├── PRD.md
│   └── tasks.md
├── tests/
│   ├── test_providers/
│   ├── test_services/
│   └── test_pipeline/
├── config/
│   └── default.yaml
├── output/
└── requirements.txt
```

---

## API Keys Required

```yaml
# config/default.yaml or .env
FAL_API_KEY=...              # Primary: VEED Fabric, Kling, sync
REPLICATE_API_TOKEN=...      # Fallback: VEED, Kling, sync
ELEVENLABS_API_KEY=...       # Hebrew TTS (direct)
ANTHROPIC_API_KEY=...        # Claude (primary LLM)
GOOGLE_API_KEY=...           # Gemini + Nano Banana Pro
```

---

## CLI Usage

```bash
# Single segment test
python -m src.main test --text "שלום עולם" --image ./ref.png

# Full video (Workflow 1)
python -m src.main generate \
  --topic "government accountability" \
  --angle "empathetic, solution-focused" \
  --image ./ref.png \
  --workflow 1

# Fast preview
python -m src.main generate --topic "..." --preview

# Use Gemini instead of Claude
python -m src.main generate --topic "..." --llm gemini
```

---

## Why This Tech Stack?

| Service | Direct API | Fal.ai | Replicate | Our Choice |
|---------|-----------|--------|-----------|------------|
| **ElevenLabs** | $0.20/1K chars | N/A | N/A | **Direct** (Hebrew voice control) |
| **VEED Fabric** | Credit-based | **$0.08/sec** | $0.10/sec | **Fal.ai** (cheaper, faster) |
| **Kling** | $1/10sec, expiring | **$0.07/sec** | $0.09/sec | **Fal.ai** (cheaper, faster) |
| **sync** | Enterprise | TBD | Pay-as-you-go | **Fal.ai** (fallback: Replicate) |

**Why Fal.ai over Replicate?**
- **Cheaper**: ~20-30% lower pricing
- **Faster**: Proprietary inference engine
- **Growing**: Backed by Sequoia ($4.5B valuation)

**Fallback Strategy**: If Fal.ai has issues, automatically switch to Replicate.

**Note on Subtitles:** We generate subtitles directly from our script text (no transcription needed).

---

## Verification Criteria

A task is marked **DONE** only when:
1. Core functionality works
2. Edge cases are handled
3. Error handling is robust
4. Schema validation passes (Instructor)
5. Tests pass

---

## Future Directions

### Near-term (Post-MVP)
- **Voice Cloning** - Clone specific Hebrew voices for brand consistency
- **Multi-Character** - Dialogues between 2+ speakers
- **Background Music** - Auto-add appropriate music/ambient sounds
- **Longer Videos** - 2-3 minute educational content

### Medium-term
- **A/B Dashboard** - Track topic/style performance metrics
- **Distribution Automation** - Auto-post to YouTube, TikTok, Instagram
- **Template Library** - Pre-built scene/style templates
- **Real-time Preview** - Generate preview as script is written

### Long-term
- **Interactive Videos** - Branching content based on viewer choices
- **Personalization** - Adapt content to viewer preferences
- **Multi-Language** - Arabic, Russian, English (Israeli demographics)
- **Live Streaming** - Real-time AI avatar broadcasts
- **Analytics Integration** - Connect with platform analytics for optimization
