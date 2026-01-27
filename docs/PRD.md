# Hebrew Democracy Video Pipeline - PRD

## Mission
Generate automated 1-minute Hebrew educational videos promoting democracy, accountability, empathy, and diverse perspectives.

---

## Tech Stack

| Component | Tool | API |
|-----------|------|-----|
| **Images** | Nano Banana Pro | Google AI |
| **Audio** | ElevenLabs V3 | ElevenLabs (he) |
| **Video + Lip-sync** | VEED Fabric 1.0 | Fal.ai |
| **Concatenation** | FFmpeg | Local |

---

## The Proper Workflow (6 Steps)

```
Step 1: Generate 3 reference images → Select best one
                    ↓
Step 2: Use reference to generate 5 scene images → Select best 3
                    ↓
Step 3: Prepare text (45-60s) → Split into 3 segments
                    ↓
Step 4: ElevenLabs Jessica: serious → urgent → angry
                    ↓
Step 5: Fabric 1.0: image + audio → video with lip-sync
                    ↓
Step 6: FFmpeg: concatenate with direct cuts
                    ↓
Output: Final video (~54 seconds)
```

### Step 1: Generate Reference Images
- Use Nano Banana Pro (`nano-banana-pro-preview`)
- Generate **3 potential reference images** of character
- Select **best one** based on:
  - Face clarity and definition
  - Hair consistency/definition
  - Lip-sync friendliness (clear mouth, no hands near face)

### Step 2: Generate Scene Images WITH Reference
- **CRITICAL**: Pass reference image to EVERY generation call
- Generate **5 scene images** at various home settings
- Ensure face, lighting, character are consistent across all 5
- Select **best 3** for the 3 video segments:
  - Segment 1: calm/neutral expression
  - Segment 2: concerned/urgent expression
  - Segment 3: intense/angry expression

### Step 3: Prepare Text
- Write or get full text for 45-60 second video
- Split into **3 parts** matching emotional arc:
  - Part 1: Setup/story (~20s)
  - Part 2: Pivot/question (~20s)
  - Part 3: Conclusion/CTA (~15s)

### Step 4: Generate Audio
- Use **ElevenLabs Jessica voice** (`EXAVITQu4vr4xnSDxMaL`)
- Emotional progression:
  - Segment 1: `serious` (natural and calm)
  - Segment 2: `urgent` (intense and emotional)
  - Segment 3: `angry` (angry and charged)

### Step 5: Generate Videos
- Use **Fabric 1.0** (`veed/fabric-1.0`) via fal.ai
- Input: segment image + segment audio
- Resolution: 720p (or 480p for faster processing)
- **Note**: ~15 seconds processing per second of audio

### Step 6: Concatenate
- Use **FFmpeg with direct cuts**
- No crossfades, no gaps between segments
- Creates punchy, news-like feel

---

## Image Generation with Reference

**The key to face consistency is ALWAYS passing the reference image.**

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=api_key)
reference_bytes = Path("selected_reference.png").read_bytes()

response = client.models.generate_content(
    model="nano-banana-pro-preview",
    contents=[
        # Pass reference image FIRST
        types.Part.from_bytes(data=reference_bytes, mime_type='image/png'),
        # Then the prompt
        """Generate a 9:16 image of this SAME woman in a living room.
        Maintain EXACT same face, hair, features from reference.
        No hands near face. Professional quality.""",
    ],
    config=types.GenerateContentConfig(response_modalities=['image', 'text'])
)
```

---

## Input/Output

**Input:**
- Topic or full script text
- Character description (for reference generation)

**Output:**
- `./output/{project}_{timestamp}/`
  - `ref_option_1-3.png` (reference options)
  - `selected_reference.png` (chosen reference)
  - `scene_1-5.png` (scene variations)
  - `segment_XX_image.png` (selected for video)
  - `segment_XX_audio.mp3` (generated audio)
  - `segment_XX_video.mp4` (lip-sync video)
  - `final_video.mp4` (concatenated)

---

## Cost Breakdown

| Step | Tool | Estimated Cost |
|------|------|----------------|
| Reference Images (3) | Nano Banana Pro | ~$0.03 |
| Scene Images (5) | Nano Banana Pro | ~$0.05 |
| Audio (54s) | ElevenLabs | ~$0.30 |
| Video (54s @ 720p) | VEED Fabric | ~$4.00 |
| **Total** | | **~$4.40** |

---

## API Keys Required

```bash
# .env file
FAL_KEY=               # Video generation (fal.ai)
ELEVENLABS_API_KEY=    # Hebrew TTS
GOOGLE_API_KEY=        # Image generation (Nano Banana Pro)
```

---

## Project Structure

```
mind-video/
├── scripts/
│   ├── proper_workflow.py    # THE main workflow
│   └── mini_test_lipsync.py  # Quick testing
├── src/
│   ├── providers/
│   │   ├── audio/elevenlabs.py
│   │   ├── image/nano_banana.py
│   │   └── video/fal/veed_fabric.py
│   └── utils/
│       ├── ffmpeg.py
│       └── video_transitions.py
├── docs/
│   ├── PRD.md                # This file
│   └── tasks.md              # Implementation tracking
├── config/default.yaml
└── output/
```

---

## CLI Usage

```bash
# Run full workflow
python scripts/proper_workflow.py all

# Run step by step
python scripts/proper_workflow.py 1  # Generate 3 ref images
python scripts/proper_workflow.py 2  # Generate 5 scenes with ref
python scripts/proper_workflow.py 3  # Prepare text
python scripts/proper_workflow.py 4  # Generate audio
python scripts/proper_workflow.py 5  # Generate videos
python scripts/proper_workflow.py 6  # Concatenate

# Quick lip-sync test
python scripts/mini_test_lipsync.py
```

---

## Future Directions

### Near-term
- Voice selection (male/female voices)
- Multi-character dialogues
- Background music/ambient sounds

### Medium-term
- A/B testing dashboard
- Distribution automation (YouTube, TikTok)
- Template library

### Long-term
- Multi-language support (Arabic, Russian, English)
- Interactive branching videos
- Real-time AI avatar streaming
