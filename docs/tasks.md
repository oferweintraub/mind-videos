# Tasks - Hebrew Democracy Video Pipeline

> A task is marked **DONE** only after thorough testing for functionality, edge cases, and robustness.

---

## Phase 1: Project Setup & Core Pipeline ✅

### 1.1 Project Setup
- [x] **1.1.1** Create project structure (src/, tests/, config/, docs/)
- [x] **1.1.2** Set up virtual environment + requirements.txt
- [x] **1.1.3** Configure API keys (.env + config loader)
- [x] **1.1.4** Set up Instructor + Pydantic for schema validation

### 1.2 Pydantic Schemas (Instructor)
- [x] **1.2.1** `schemas/segment.py` - Segment model (text, duration, scene)
- [x] **1.2.2** `schemas/script.py` - Full script model (segments, metadata)
- [x] **1.2.3** `schemas/scene.py` - Scene definition (camera, lighting, expression)
- [x] **1.2.4** `schemas/validation.py` - Quality validation response

### 1.3 Provider Base Classes
- [x] **1.3.1** `providers/base.py` - Abstract interfaces for all providers
- [x] **1.3.2** Define common error handling and retry logic

### 1.4 ElevenLabs Provider
- [x] **1.4.1** `providers/audio/elevenlabs.py` - Basic TTS implementation
- [x] **1.4.2** Hebrew voice configuration (Jessica, male voice)
- [x] **1.4.3** Handle long text chunking (>5000 chars)
- [ ] **1.4.4** Test with Hebrew text edge cases (special chars, numbers)
- [ ] **1.4.5** Write unit tests

### 1.5 Video Provider Base & VEED Fabric
- [x] **1.5.1** `providers/video/base_video.py` - Abstract video interface
- [x] **1.5.2** `providers/video/fal/veed_fabric.py` - Fal.ai implementation (primary)
- [x] **1.5.3** `providers/video/replicate/veed_fabric.py` - Replicate fallback
- [x] **1.5.4** Handle image + audio upload for both providers
- [x] **1.5.5** Poll for completion, download result
- [x] **1.5.6** Automatic fallback: Fal.ai → Replicate on failure
- [x] **1.5.7** Error handling (timeout, API errors, rate limits)
- [ ] **1.5.8** Test with various image sizes/formats
- [ ] **1.5.9** Write unit tests for both providers

### 1.6 Core Pipeline Integration
- [x] **1.6.1** `pipeline/orchestrator.py` - Basic single-segment flow
- [x] **1.6.2** CLI: `python -m src.main test --text "..." --image X`
- [ ] **1.6.3** End-to-end test: text + image → audio → video

---

## Phase 2: LLM Integration ✅

### 2.1 Claude Provider
- [x] **2.1.1** `providers/llm/claude.py` - Basic Claude API wrapper
- [x] **2.1.2** Integrate Instructor for structured outputs
- [ ] **2.1.3** Test schema validation with complex Hebrew text
- [ ] **2.1.4** Write unit tests

### 2.2 Gemini Provider (Drop-in)
- [x] **2.2.1** `providers/llm/gemini.py` - Same interface as Claude
- [x] **2.2.2** Integrate Instructor for structured outputs
- [ ] **2.2.3** Test compatibility with Claude outputs
- [ ] **2.2.4** Write unit tests

### 2.3 Script Generator Service
- [x] **2.3.1** `services/script_generator.py` - Generate 3 script options
- [x] **2.3.2** Prompt engineering for Hebrew educational content
- [x] **2.3.3** Segment text into 6-8 chunks (8-10 sec each)
- [x] **2.3.4** LLM-as-judge: auto-select best script
- [ ] **2.3.5** Test with various topics
- [ ] **2.3.6** Write unit tests

### 2.4 Scene Planner Service
- [x] **2.4.1** `services/scene_planner.py` - Define scene per segment
- [x] **2.4.2** Output: camera, lighting, expression, setting
- [x] **2.4.3** Ensure variety across segments
- [ ] **2.4.4** Test scene consistency
- [ ] **2.4.5** Write unit tests

---

## Phase 3: Image Generation & Full Pipeline ✅

### 3.1 Nano Banana Pro Provider (Google)
- [x] **3.1.1** `providers/image/nano_banana.py` - Google AI integration
- [x] **3.1.2** Character consistency with reference image
- [x] **3.1.3** Generate images for different scene settings
- [ ] **3.1.4** Test image quality and consistency
- [ ] **3.1.5** Write unit tests

### 3.2 Quality Validator Service
- [x] **3.2.1** `services/quality_validator.py` - LLM video analysis
- [x] **3.2.2** Score: lip-sync, face visibility, consistency
- [x] **3.2.3** Decision: approve or request remake
- [ ] **3.2.4** Test with good/bad video samples
- [ ] **3.2.5** Write unit tests

### 3.3 Subtitle Generator Service
- [x] **3.3.1** `services/subtitle_generator.py` - Generate SRT
- [x] **3.3.2** Hebrew RTL encoding
- [x] **3.3.3** Configurable styling (font, size, color, background)
- [ ] **3.3.4** Test with various Hebrew texts
- [ ] **3.3.5** Write unit tests

### 3.4 FFMPEG Utils
- [x] **3.4.1** `utils/ffmpeg.py` - Concatenation function
- [x] **3.4.2** Burn subtitles into video
- [x] **3.4.3** Fade in/out transitions
- [x] **3.4.4** Extract thumbnails
- [ ] **3.4.5** Test with various video formats
- [ ] **3.4.6** Write unit tests

### 3.5 Metadata Tracking
- [x] **3.5.1** `utils/metadata.py` - YAML generation
- [x] **3.5.2** Track all A/B testing data
- [x] **3.5.3** Cost tracking per video
- [ ] **3.5.4** Write unit tests

### 3.6 Workflow 1 Complete
- [x] **3.6.1** `pipeline/workflow1.py` - Full image-based workflow
- [x] **3.6.2** Multi-segment orchestration
- [x] **3.6.3** Remake logic for failed segments
- [x] **3.6.4** Preview mode (3-4 segments)
- [ ] **3.6.5** End-to-end test: topic → full video
- [ ] **3.6.6** Write integration tests

---

## Phase 4: Workflow 2 & Polish ✅

### 4.1 Kling 2.5 Pro Provider (Fal.ai + Replicate)
- [x] **4.1.1** `providers/video/fal/kling.py` - Fal.ai implementation (primary)
- [x] **4.1.2** `providers/video/replicate/kling.py` - Replicate fallback
- [x] **4.1.3** Motion prompt handling for both providers
- [x] **4.1.4** Automatic fallback: Fal.ai → Replicate on failure
- [ ] **4.1.5** Test video quality
- [ ] **4.1.6** Write unit tests for both providers

### 4.2 sync/lipsync-2-pro Provider (Fal.ai + Replicate)
- [x] **4.2.1** `providers/video/fal/sync_lipsync.py` - Fal.ai implementation (primary)
- [x] **4.2.2** `providers/video/replicate/sync_lipsync.py` - Replicate fallback
- [x] **4.2.3** Handle video upload for both providers
- [x] **4.2.4** Automatic fallback: Fal.ai → Replicate on failure
- [ ] **4.2.5** Test lip-sync accuracy
- [ ] **4.2.6** Write unit tests for both providers

### 4.3 Workflow 2 Complete
- [x] **4.3.1** `pipeline/workflow2.py` - Full video-based workflow
- [x] **4.3.2** Integration with Kling + sync
- [ ] **4.3.3** End-to-end test
- [ ] **4.3.4** Write integration tests

### 4.4 CLI Polish
- [x] **4.4.1** Full CLI with all options
- [x] **4.4.2** Progress indicators
- [x] **4.4.3** Error messages
- [x] **4.4.4** Help documentation

---

## Phase 5: Content Brief System ✅

### 5.1 ContentBrief Schema
- [x] **5.1.1** `schemas/brief.py` - ContentBrief Pydantic model
- [x] **5.1.2** EmotionalTone enum (angry, hopeful, cynical, etc.)
- [x] **5.1.3** RhetoricalDevice enum (metaphors, rhetorical_questions, etc.)
- [x] **5.1.4** Key points, rhetorical questions, must-include phrases
- [x] **5.1.5** `to_prompt_context()` - Convert brief to Hebrew LLM prompt
- [x] **5.1.6** `from_yaml()` and `from_markdown()` - File loading

### 5.2 ScriptRequest Integration
- [x] **5.2.1** Update ScriptRequest to accept optional ContentBrief
- [x] **5.2.2** `get_prompt_context()` - Return detailed or simple context
- [x] **5.2.3** `from_brief_file()` - Factory method for file loading
- [x] **5.2.4** Validation: require either (topic+angle) or brief

### 5.3 Pipeline Integration
- [x] **5.3.1** Update Workflow1Pipeline.run() to accept brief
- [x] **5.3.2** Update Workflow2Pipeline.run() to accept brief
- [x] **5.3.3** Store brief in metadata for tracking
- [x] **5.3.4** Pass prompt_context to script generator

### 5.4 LLM Provider Updates
- [x] **5.4.1** Update Claude generate_script_options() for prompt_context
- [x] **5.4.2** Update Gemini generate_script_options() for prompt_context
- [x] **5.4.3** Enhanced prompts: follow key points, use tone, incorporate devices

### 5.5 CLI Updates
- [x] **5.5.1** Add `--brief` / `-b` option to generate command
- [x] **5.5.2** Support YAML and Markdown brief formats
- [x] **5.5.3** Display mode (Detailed Brief vs Simple) in output
- [x] **5.5.4** Make topic/angle optional when brief provided

### 5.6 Sample Briefs
- [x] **5.6.1** `briefs/october7_investigation.yaml` - Example brief
- [x] **5.6.2** `briefs/example_template.md` - Markdown template
- [ ] **5.6.3** Additional sample briefs for different topics
- [ ] **5.6.4** Brief validation tests

---

## Phase 6: Error Handling Improvements ✅

### 6.1 Circuit Breaker Pattern
- [x] **6.1.1** `CircuitBreakerConfig` - Configurable failure threshold and recovery
- [x] **6.1.2** `CircuitState` enum (CLOSED, OPEN, HALF_OPEN)
- [x] **6.1.3** Auto-open circuit after consecutive failures
- [x] **6.1.4** Auto-recovery with half-open testing
- [x] **6.1.5** `ProviderStatus` now actively updated (AVAILABLE → DEGRADED → UNAVAILABLE)
- [x] **6.1.6** `_check_circuit()` - Fast-fail when circuit open

### 6.2 Structured Batch Error Handling
- [x] **6.2.1** `BatchResult` - Container for batch operation results
- [x] **6.2.2** `BatchItemResult` - Individual item success/failure tracking
- [x] **6.2.3** Helper methods: `successful_items`, `failed_items`, `get_errors()`
- [x] **6.2.4** `NanoBananaProvider.generate_batch()` - Structured results
- [x] **6.2.5** `ElevenLabsProvider.generate_batch()` - Structured results
- [x] **6.2.6** `fail_fast` option to stop batch on first error
- [x] **6.2.7** Legacy compatibility methods for backwards support

### 6.3 Per-Operation Timeout Configuration
- [x] **6.3.1** `TimeoutConfig` - Operation-specific timeouts
- [x] **6.3.2** `health_check`: 10s (was 60s)
- [x] **6.3.3** `audio_generation`: 120s
- [x] **6.3.4** `image_generation`: 120s
- [x] **6.3.5** `video_generation`: 300s (was 60s)
- [x] **6.3.6** `video_polling`: 600s (was 60s)
- [x] **6.3.7** `get_timeout_for_operation()` helper method

### 6.4 Provider Status Integration
- [x] **6.4.1** `_record_success()` - Reset circuit on success
- [x] **6.4.2** `_record_failure()` - Track failures, update status
- [x] **6.4.3** Circuit state in `ProviderResult.metadata`
- [ ] **6.4.4** Unit tests for circuit breaker behavior
- [ ] **6.4.5** Integration tests for batch error handling

---

## Phase 7: Reference Image Workflow ✅

> **Current workflow**: Generate reference → use reference for all scene images → select best 3 → video generation

### 7.1 Reference Image Generation
- [x] **7.1.1** Generate 3 potential reference images with Nano Banana Pro
- [x] **7.1.2** Selection criteria: face clarity, hair definition, lip-sync friendliness
- [x] **7.1.3** Save selected reference as `selected_reference.png`
- [x] **7.1.4** Implemented in `scripts/proper_workflow.py` Step 1

### 7.2 Scene Image Generation WITH Reference
- [x] **7.2.1** Pass reference image bytes to EVERY scene generation call
- [x] **7.2.2** Generate 5 scene images at various home settings
- [x] **7.2.3** Maintain face, lighting, character consistency across all 5
- [x] **7.2.4** Select best 3 images for the 3 video segments
- [x] **7.2.5** Implemented in `scripts/proper_workflow.py` Step 2

### 7.3 Provider Implementation
- [x] **7.3.1** `NanoBananaProvider.generate_image()` with reference_image parameter
- [x] **7.3.2** Pass reference as `types.Part.from_bytes()` in contents
- [x] **7.3.3** Prompt engineering for face consistency ("this SAME woman", "EXACT same face")
- [x] **7.3.4** Tested and working in production

### 7.4 Workflow Script
- [x] **7.4.1** `scripts/proper_workflow.py` - Full 6-step workflow
- [x] **7.4.2** Step-by-step execution: `python scripts/proper_workflow.py [1-6|all]`
- [x] **7.4.3** Auto-selection of reference and scene images
- [x] **7.4.4** Integration with ElevenLabs audio (serious → urgent → angry)
- [x] **7.4.5** Integration with VEED Fabric video generation
- [x] **7.4.6** FFmpeg concatenation with direct cuts

---

## Phase 8: Quality Refinement 🎯 HIGH PRIORITY

> **Tomorrow's Focus:** Go through these one by one to achieve smooth, lifelike results.

### 8.1 Lip-sync Quality
- [ ] **8.1.1** Evaluate VEED Fabric lip-sync accuracy on Hebrew speech
- [ ] **8.1.2** Test alternative lip-sync models (sync/lipsync-2-pro)
- [ ] **8.1.3** Experiment with audio preprocessing for better sync
- [ ] **8.1.4** Document optimal settings for Hebrew content

### 8.2 Character Consistency
- [ ] **8.2.1** Fine-tune Nano Banana Pro prompts for better face consistency
- [ ] **8.2.2** Test prompt variations for expression control
- [ ] **8.2.3** Evaluate mosaic grid size (2x3 vs 3x3)
- [ ] **8.2.4** Document best practices for character prompts

### 8.3 Transition Timing
- [ ] **8.3.1** Test fade duration variations (0.3s, 0.5s, 0.7s)
- [ ] **8.3.2** Experiment with transition types (fade, dissolve, wipe)
- [ ] **8.3.3** Optimize natural continuation between same-image segments
- [ ] **8.3.4** Add configurable transition settings

### 8.4 Audio Pacing & Emotion
- [ ] **8.4.1** Test ElevenLabs v3 stability/similarity settings
- [ ] **8.4.2** Experiment with speech rate adjustments
- [ ] **8.4.3** Test emotional tone variations (serious, determined, empathetic)
- [ ] **8.4.4** Add per-segment voice settings support

### 8.5 Resolution & Final Quality
- [ ] **8.5.1** Test 720p output quality vs 480p
- [ ] **8.5.2** Evaluate cost/quality tradeoff at higher resolution
- [ ] **8.5.3** Add resolution selection to CLI
- [ ] **8.5.4** Final output optimization (bitrate, codec settings)

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
| Phase 1: Setup & Core | 21 | 17 | 81% |
| Phase 2: LLM | 16 | 10 | 63% |
| Phase 3: Full Pipeline | 20 | 14 | 70% |
| Phase 4: Workflow 2 | 16 | 12 | 75% |
| Phase 5: Content Brief | 20 | 18 | 90% |
| Phase 6: Error Handling | 19 | 17 | 89% |
| Phase 7: Reference Image Workflow | 16 | 16 | 100% |
| Phase 8: Quality Refinement | 17 | 0 | 0% |
| **Total** | **145** | **104** | **72%** |

> **Current Status:** Phase 7 (Reference Image Workflow) complete and working via `scripts/proper_workflow.py`.
> **Next Priority:** Phase 8 - Quality Refinement (lip-sync tuning, transition timing, audio pacing).
