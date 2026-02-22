# Lessons Learned

> **MANDATORY**: Read this file before starting any coding task.
> Keep each section to **50 lines max**. When adding new entries, remove the least important if over the cap.

---

## Things That Work Well

- **[Kokoro TTS]**: `kokoro-js` via Node.js bridge works great for English TTS. Use `af_heart` voice. Generate WAV then convert to MP3 with ffmpeg externally — `process.exit(0)` after save doesn't flush, and without it the phonemizer wasm crashes on cleanup but the WAV file is fine.
- **[fal_client.run_async]**: For image generation (Qwen, Qwen Max, FLUX), `run_async` is simpler than submit+poll. For video generation, use `submit_async` + manual polling since it takes minutes.
- **[Parallel combo execution]**: Running multiple combos in parallel background processes works well. Each combo is independent.
- **[File existence checks]**: Checking if files exist before generating (skip if exists) makes reruns fast and resumable.
- **[VEED Fabric 1.0]**: Reliable and fast lip-sync. ~1-2 min per video at 480p. Works with all image models AND stylized input (cartoons, puppets, comics, sketches). Preserves artistic style.
- **[Qwen Image Max with ref]**: `fal-ai/qwen-image-max/text-to-image` for reference, `fal-ai/qwen-image-max/edit` with `image_urls: [ref_url]` for scenes. Unlike Qwen-2512, Max supports reference images. $0.075/image.
- **[Kling 2.6 Pro]**: `fal-ai/kling-video/v2.6/pro/image-to-video` — uses `start_image_url` (not `image_url` like v2.1). $0.07/s without audio. Good motion quality, ~1-2 min per 10s clip.
- **[ElevenLabs Voice Cloning]**: IVC via `POST /v1/voices/add` with multipart audio files. Needs `Voices → Write` API key permission. Cloning itself is free (no TTS credits consumed). 3 clips of ~90s each per character works well.
- **[yt-dlp YouTube download]**: Keep yt-dlp updated (`brew upgrade yt-dlp`) — old versions get 403 from YouTube SABR streaming. Extract audio with `-x --audio-format mp3`. Use ffmpeg to cut clips: `ffmpeg -i input.mp3 -ss START -t DURATION -acodec libmp3lame clip.mp3`.
- **[Nano Banana + puppet ref for expressions]**: Using an existing puppet image as reference in Nano Banana Pro produces highly consistent expression variants. Prompt pattern: "Generate this EXACT SAME puppet. Change ONLY the expression to: [expression]. Keep everything else identical." Much better than text-only for consistency across scenes.
- **[Hebrew pronunciation with niqqud]**: Adding Hebrew niqqud (vowel marks) to ambiguous words improves ElevenLabs pronunciation. E.g., "אַחֲרַי" instead of "אחרי", "מָשכו בדַש" instead of "משכו בדש".
- **[Tempo post-processing: track newly_generated]**: When applying ffmpeg atempo to audio in a skip-if-exists pipeline, ONLY apply to newly generated files. Applying to all files causes double-speed on incremental reruns. Use a `newly_generated` list to track which files were just created.

---

## Things That Need Solving

- **[Hebrew TTS pronunciation + emotion]**: ElevenLabs cloned voices with `eleven_v3` produce decent Hebrew but struggle with correct pronunciation of uncommon words and emotional intonation. Niqqud helps but doesn't fully solve it. Speech-to-speech (recording a human reading the lines with correct emotion/pronunciation, then converting to the cloned voice) could be a much better approach for getting both Hebrew accuracy and emotional delivery right. Investigate ElevenLabs speech-to-speech or similar tools.

---

## Things That DO NOT Work

- **[Kling model IDs]**: Always include the full endpoint path. Examples: `fal-ai/kling-video/v2.1/standard/image-to-video`, `fal-ai/kling-video/v2.6/pro/image-to-video`. Also `fal-ai/sync-lipsync/v2` (not `sync-lipsync-2-pro`).
- **[Kling LipSync endpoint]**: `fal-ai/kling-video/lipsync/audio-to-video` requires VIDEO+audio, NOT image+audio. For image+audio→video use `fal-ai/kling-video/ai-avatar/v2/standard` instead.
- **[httpx default timeout]**: `httpx.AsyncClient()` defaults to 5s timeout which is too short for downloading fal.ai generated images. Always use `httpx.AsyncClient(timeout=60.0)`.
- **[kokoro-js ESM import]**: `import { KokoroTTS } from "kokoro-js"` fails across directories. Use `createRequire()` to load from the correct `node_modules` path.
- **[Node.js process.exit(0) before file flush]**: Calling `process.exit(0)` after `audio.save()` in kokoro can terminate before the file is flushed to disk. Just let the process exit naturally — the wasm crash is harmless.
- **[Qwen-Image-2512 is outdated]**: `fal-ai/qwen-image-2512` is an older model with no reference image support. Use `fal-ai/qwen-image-max` instead — it has `/edit` endpoint for reference images and better realism.
- **[Seedance 2.0 not on fal.ai yet]**: As of Feb 2026, Seedance 2.0 is NOT available via API anywhere (despite marketing claims from aggregators). Official ByteDance API launches ~Feb 24 via Volcengine. Check fal.ai for `fal-ai/bytedance/seedance/v2` after that date.
- **[2-step lipsync is fundamentally worse]**: Kling motion → Sync Lipsync overlay produces bad lip-sync because the lipsync model fights the existing mouth movements. VEED Fabric's one-step (image+audio→video) is far better for talking heads. Don't use 2-step pipelines for speech content.
- **[Qwen Max /edit doesn't lock faces]**: `fal-ai/qwen-image-max/edit` with reference image treats it as a style guide, NOT face-lock. Character drifts between scenes. Nano Banana Pro's reference support is much stronger.
- **[ElevenLabs multilingual_v2 + language_code]**: `eleven_multilingual_v2` does NOT support `language_code='he'` — returns 400 error. Don't pass `language_code` for this model; it auto-detects language from text. Only `eleven_v3` supports explicit language codes.

---

## Patterns & Conventions

- **Provider pattern**: All fal.ai providers extend `ExtendedVideoProvider` with `_submit_job`, `_check_job_status`, `_download_video` methods.
- **Image providers**: Extend `BaseImageProvider` with `generate_image(prompt, reference_image, output_path)`.
- **fal.ai upload**: Use `fal_client.upload_async(bytes, content_type=...)` to get a CDN URL before submitting jobs.
- **Video polling**: Submit with `submit_async`, poll with `status_async` checking `isinstance(status, fal_client.Completed)`, get result with `result_async`.
- **Output structure**: `output/<workflow_name>/combo_<N>_<name>/` with `reference.png`, `scene_XX.png`, `video_XX.mp4`, `final.mp4`, `metadata.json`.
- **Stylized image models on fal.ai**: Cartoonify (`fal-ai/cartoonify`, $0.10/img, Pixar-style), Ghiblify (`fal-ai/ghiblify`, $0.05/img), FLUX Digital Comic Art (`fal-ai/flux-2-lora-gallery/digital-comic-art`, $0.021/MP, trigger `d1g1t4l`), Instant Character (`fal-ai/instant-character`, $0.10/MP, best consistency), FLUX Kontext Pro (`fal-ai/flux-pro/kontext`, $0.04/img, 89% consistency).
- **Production pipeline**: For any character style — generate stylized image → VEED Fabric 1.0 (image+audio→lip-synced video) → FFmpeg concat. Works for photorealistic, puppets, comics, cartoons.
- **[Puppet image gen]**: Nano Banana Pro text-only is best for puppet generation. FLUX.2 Pro has better felt texture but worse character recognition. Named politicians work in prompts. Personality traits ("sleazy", "sycophantic") effectively shape expressions.
- **[Nano Banana + real ref photos for puppets]**: Real reference photos override puppet style — results too photorealistic. Ref photos of women + caricature prompts get blocked by safety filter. Use text-only OR puppet-as-reference (see "Things That Work Well").
- **[Downloading images from web]**: Wikimedia and most image sites block automated downloads. Don't waste time trying to curl/wget — have the user provide reference photos or generate synthetic refs.
