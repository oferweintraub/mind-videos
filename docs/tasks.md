# Tasks - Hebrew Democracy Video Pipeline

> A task is marked **DONE** only after thorough testing for functionality, edge cases, and robustness.

---

## Phase 1: Project Setup & Core Pipeline

### 1.1 Project Setup
- [ ] **1.1.1** Create project structure (src/, tests/, config/, docs/)
- [ ] **1.1.2** Set up virtual environment + requirements.txt
- [ ] **1.1.3** Configure API keys (.env + config loader)
- [ ] **1.1.4** Set up Instructor + Pydantic for schema validation

### 1.2 Pydantic Schemas (Instructor)
- [ ] **1.2.1** `schemas/segment.py` - Segment model (text, duration, scene)
- [ ] **1.2.2** `schemas/script.py` - Full script model (segments, metadata)
- [ ] **1.2.3** `schemas/scene.py` - Scene definition (camera, lighting, expression)
- [ ] **1.2.4** `schemas/validation.py` - Quality validation response

### 1.3 Provider Base Classes
- [ ] **1.3.1** `providers/base.py` - Abstract interfaces for all providers
- [ ] **1.3.2** Define common error handling and retry logic

### 1.4 ElevenLabs Provider
- [ ] **1.4.1** `providers/audio/elevenlabs.py` - Basic TTS implementation
- [ ] **1.4.2** Hebrew voice configuration (Jessica, male voice)
- [ ] **1.4.3** Handle long text chunking (>5000 chars)
- [ ] **1.4.4** Test with Hebrew text edge cases (special chars, numbers)
- [ ] **1.4.5** Write unit tests

### 1.5 Video Provider Base & VEED Fabric
- [ ] **1.5.1** `providers/video/base_video.py` - Abstract video interface
- [ ] **1.5.2** `providers/video/fal/veed_fabric.py` - Fal.ai implementation (primary)
- [ ] **1.5.3** `providers/video/replicate/veed_fabric.py` - Replicate fallback
- [ ] **1.5.4** Handle image + audio upload for both providers
- [ ] **1.5.5** Poll for completion, download result
- [ ] **1.5.6** Automatic fallback: Fal.ai → Replicate on failure
- [ ] **1.5.7** Error handling (timeout, API errors, rate limits)
- [ ] **1.5.8** Test with various image sizes/formats
- [ ] **1.5.9** Write unit tests for both providers

### 1.6 Core Pipeline Integration
- [ ] **1.6.1** `pipeline/orchestrator.py` - Basic single-segment flow
- [ ] **1.6.2** CLI: `python -m src.main test --text "..." --image X`
- [ ] **1.6.3** End-to-end test: text + image → audio → video

---

## Phase 2: LLM Integration

### 2.1 Claude Provider
- [ ] **2.1.1** `providers/llm/claude.py` - Basic Claude API wrapper
- [ ] **2.1.2** Integrate Instructor for structured outputs
- [ ] **2.1.3** Test schema validation with complex Hebrew text
- [ ] **2.1.4** Write unit tests

### 2.2 Gemini Provider (Drop-in)
- [ ] **2.2.1** `providers/llm/gemini.py` - Same interface as Claude
- [ ] **2.2.2** Integrate Instructor for structured outputs
- [ ] **2.2.3** Test compatibility with Claude outputs
- [ ] **2.2.4** Write unit tests

### 2.3 Script Generator Service
- [ ] **2.3.1** `services/script_generator.py` - Generate 3 script options
- [ ] **2.3.2** Prompt engineering for Hebrew educational content
- [ ] **2.3.3** Segment text into 6-8 chunks (8-10 sec each)
- [ ] **2.3.4** LLM-as-judge: auto-select best script
- [ ] **2.3.5** Test with various topics
- [ ] **2.3.6** Write unit tests

### 2.4 Scene Planner Service
- [ ] **2.4.1** `services/scene_planner.py` - Define scene per segment
- [ ] **2.4.2** Output: camera, lighting, expression, setting
- [ ] **2.4.3** Ensure variety across segments
- [ ] **2.4.4** Test scene consistency
- [ ] **2.4.5** Write unit tests

---

## Phase 3: Image Generation & Full Pipeline

### 3.1 Nano Banana Pro Provider (Google)
- [ ] **3.1.1** `providers/image/nano_banana.py` - Google AI integration
- [ ] **3.1.2** Character consistency with reference image
- [ ] **3.1.3** Generate images for different scene settings
- [ ] **3.1.4** Test image quality and consistency
- [ ] **3.1.5** Write unit tests

### 3.2 Quality Validator Service
- [ ] **3.2.1** `services/quality_validator.py` - LLM video analysis
- [ ] **3.2.2** Score: lip-sync, face visibility, consistency
- [ ] **3.2.3** Decision: approve or request remake
- [ ] **3.2.4** Test with good/bad video samples
- [ ] **3.2.5** Write unit tests

### 3.3 Subtitle Generator Service
- [ ] **3.3.1** `services/subtitle_generator.py` - Generate SRT
- [ ] **3.3.2** Hebrew RTL encoding
- [ ] **3.3.3** Configurable styling (font, size, color, background)
- [ ] **3.3.4** Test with various Hebrew texts
- [ ] **3.3.5** Write unit tests

### 3.4 FFMPEG Utils
- [ ] **3.4.1** `utils/ffmpeg.py` - Concatenation function
- [ ] **3.4.2** Burn subtitles into video
- [ ] **3.4.3** Fade in/out transitions
- [ ] **3.4.4** Extract thumbnails
- [ ] **3.4.5** Test with various video formats
- [ ] **3.4.6** Write unit tests

### 3.5 Metadata Tracking
- [ ] **3.5.1** `utils/metadata.py` - YAML generation
- [ ] **3.5.2** Track all A/B testing data
- [ ] **3.5.3** Cost tracking per video
- [ ] **3.5.4** Write unit tests

### 3.6 Workflow 1 Complete
- [ ] **3.6.1** `pipeline/workflow1.py` - Full image-based workflow
- [ ] **3.6.2** Multi-segment orchestration
- [ ] **3.6.3** Remake logic for failed segments
- [ ] **3.6.4** Preview mode (3-4 segments)
- [ ] **3.6.5** End-to-end test: topic → full video
- [ ] **3.6.6** Write integration tests

---

## Phase 4: Workflow 2 & Polish

### 4.1 Kling 2.5 Pro Provider (Fal.ai + Replicate)
- [ ] **4.1.1** `providers/video/fal/kling.py` - Fal.ai implementation (primary)
- [ ] **4.1.2** `providers/video/replicate/kling.py` - Replicate fallback
- [ ] **4.1.3** Motion prompt handling for both providers
- [ ] **4.1.4** Automatic fallback: Fal.ai → Replicate on failure
- [ ] **4.1.5** Test video quality
- [ ] **4.1.6** Write unit tests for both providers

### 4.2 sync/lipsync-2-pro Provider (Fal.ai + Replicate)
- [ ] **4.2.1** `providers/video/fal/sync_lipsync.py` - Fal.ai implementation (primary)
- [ ] **4.2.2** `providers/video/replicate/sync_lipsync.py` - Replicate fallback
- [ ] **4.2.3** Handle video upload for both providers
- [ ] **4.2.4** Automatic fallback: Fal.ai → Replicate on failure
- [ ] **4.2.5** Test lip-sync accuracy
- [ ] **4.2.6** Write unit tests for both providers

### 4.3 Workflow 2 Complete
- [ ] **4.3.1** `pipeline/workflow2.py` - Full video-based workflow
- [ ] **4.3.2** Integration with Kling + sync
- [ ] **4.3.3** End-to-end test
- [ ] **4.3.4** Write integration tests

### 4.4 CLI Polish
- [ ] **4.4.1** Full CLI with all options
- [ ] **4.4.2** Progress indicators
- [ ] **4.4.3** Error messages
- [ ] **4.4.4** Help documentation

---

## Testing Checklist (Per Task)

Before marking any task DONE:

- [ ] Unit tests pass
- [ ] Edge cases covered (empty input, long text, special chars)
- [ ] Error handling works (network errors, API errors, timeouts)
- [ ] Schema validation passes (Instructor/Pydantic)
- [ ] Hebrew-specific cases tested (RTL, special consonants)
- [ ] Integration with other components verified

---

## Progress Tracking

| Phase | Tasks | Done | Progress |
|-------|-------|------|----------|
| Phase 1: Setup & Core | 21 | 0 | 0% |
| Phase 2: LLM | 16 | 0 | 0% |
| Phase 3: Full Pipeline | 20 | 0 | 0% |
| Phase 4: Workflow 2 | 16 | 0 | 0% |
| **Total** | **73** | **0** | **0%** |
