# Lessons Learned

> **MANDATORY**: Read this file before starting any coding task.
> Keep each section to **50 lines max**. When adding new entries, remove the least important if over the cap.

---

## Things That Work Well

- **[Kokoro TTS]**: `kokoro-js` via Node.js bridge works great for English TTS. Use `af_heart` voice. Generate WAV then convert to MP3 with ffmpeg externally — `process.exit(0)` after save doesn't flush, and without it the phonemizer wasm crashes on cleanup but the WAV file is fine.
- **[fal_client.run_async]**: For image generation (Qwen, Qwen Max, FLUX), `run_async` is simpler than submit+poll. For video generation, use `submit_async` + manual polling since it takes minutes.
- **[Parallel combo execution]**: Running multiple combos in parallel background processes works well. Each combo is independent.
- **[File existence checks]**: Checking if files exist before generating (skip if exists) makes reruns fast and resumable.
- **[VEED Fabric 1.0]**: Reliable and fast lip-sync. ~1-2 min per video at 480p. Works with all image models AND stylized input (cartoons, puppets, comics, sketches). Preserves artistic style. Best price/quality sweet spot for Hebrew lip-sync at $0.08/s (480p). See lip-sync comparison below.
- **[Qwen Image Max with ref]**: `fal-ai/qwen-image-max/text-to-image` for reference, `fal-ai/qwen-image-max/edit` with `image_urls: [ref_url]` for scenes. Unlike Qwen-2512, Max supports reference images. $0.075/image.
- **[Kling 2.6 Pro]**: `fal-ai/kling-video/v2.6/pro/image-to-video` — uses `start_image_url` (not `image_url` like v2.1). $0.07/s without audio. Good motion quality, ~1-2 min per 10s clip.
- **[ElevenLabs Voice Cloning]**: IVC via `POST /v1/voices/add` with multipart audio files. Needs `Voices → Write` API key permission. Cloning itself is free (no TTS credits consumed). 3 clips of ~90s each per character works well.
- **[yt-dlp YouTube download]**: Keep yt-dlp updated (`brew upgrade yt-dlp`) — old versions get 403 from YouTube SABR streaming. Extract audio with `-x --audio-format mp3`. Use ffmpeg to cut clips: `ffmpeg -i input.mp3 -ss START -t DURATION -acodec libmp3lame clip.mp3`.
- **[Nano Banana + puppet ref for expressions]**: Using an existing puppet image as reference in Nano Banana Pro produces highly consistent expression variants. Prompt pattern: "Generate this EXACT SAME puppet. Change ONLY the expression to: [expression]. Keep everything else identical." Much better than text-only for consistency across scenes.
- **[Nano Banana + style variants]**: Cartoon caricature style works great text-only for recognizable politicians. Anime style does NOT produce recognizable faces text-only — must pass puppet/reference image to Nano Banana to maintain identity. Anime + reference = good results.
- **[Bibi voice 1.25x tempo]**: Bibi's natural speaking pace is faster than ElevenLabs default output. Apply `ffmpeg -filter:a atempo=1.25` after generation for more natural cadence.
- **[Hebrew pronunciation with niqqud]**: Adding Hebrew niqqud (vowel marks) to ambiguous words improves ElevenLabs pronunciation. E.g., "אַחֲרַי" instead of "אחרי", "מָשכו בדַש" instead of "משכו בדש".
- **[Tempo post-processing: track newly_generated]**: When applying ffmpeg atempo to audio in a skip-if-exists pipeline, ONLY apply to newly generated files. Applying to all files causes double-speed on incremental reruns. Use a `newly_generated` list to track which files were just created.
- **[Chatterbox S2S for Hebrew voice conversion]**: `fal-ai/chatterbox/speech-to-speech` is the best option for Hebrew speech-to-speech voice conversion. Record human reading lines with correct pronunciation/emotion, then convert to cloned voice. Uses `source_audio_url` + `target_voice_audio_url` (a reference clip of the target voice). Clip2 from voice cloning source audio works best as reference. Language-agnostic — preserves Hebrew delivery. ElevenLabs STS does NOT work for Hebrew (passes audio through unchanged). Resemble AI S2S works but Chatterbox produces better results.
- **[Slash commands as primary UX (Cowork)]**: For non-coder workflows, `.claude/commands/<name>.md` files paired with Claude Cowork beat building a custom UI. Cowork's chat interface IS the UI — conversational ("make her hair red instead", "try one more variant") is more flexible than form-based, and every new capability is just a markdown file, not a UI rebuild. Validated end-to-end on the character → script → video flow.
- **[Manifest-driven character library + Markdown script.md]**: Decoupling characters (JSON manifest + image) from scripts (Markdown with `## <slug>` headings) lets the same pipeline render any cast. Characters become reusable across episodes; scripts become human-readable. The `episodes/<slug>/{script.md, audio/, videos/, final.mp4}` layout makes each episode self-contained — easy to delete, share, or regenerate.
- **[Idempotent pipeline survives reorg]**: Because `src/pipeline/episode.py` already used skip-if-exists everywhere, a major restructure (hardcoded cast → manifest-driven library) only required changing the *calling layer*. Pipeline functions worked unchanged. Strong evidence the early decision to make every step idempotent was correct.
- **[Streamlit + Supabase for cloud-backed wizards]**: The pairing handles state persistence, share links, and storage cleanly. RLS-off + unguessable 12-char IDs is acceptable for the "URL-is-the-bearer-token" trust model (Excalidraw / jsonbin). New `sb_publishable_*` keys work with the Python SDK. SQL setup can be driven via Playwright + Monaco's `setValue()` API for one-time installs.
- **[Per-session API key isolation]**: Read keys from `st.session_state` only (never write to `os.environ` from per-user UI). Pipeline functions take explicit `*, api_key=` kwargs. Solves multi-tenant key leakage on Streamlit Cloud's shared-process model. Strip whitespace defensively in the reader — copy-paste introduces 401s.
- **[Friendly-error helper module]**: One central module mapping common provider failures (ElevenLabs 401/403/429, fal.ai 401/403, Google API_KEY_INVALID/SAFETY/quota, ffmpeg, network) to actionable Markdown beats raw tracebacks. Cuts user diagnosis time from minutes to seconds. Keep raw exception in `<details>` for inspection.
- **[`go_to(N)` over direct step assignment]**: Wrap step transitions in a single helper that updates session_state AND calls auto_save. Direct `st.session_state.step = N` assignments race with auto_save reads — they may fire before the save sees the new value. One canonical mutator avoids the bug class.

---

## Things That Need Solving

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
- **[LatentSync unusable for Hebrew]**: `fal-ai/latentsync` ($0.20 flat for ≤40s) produces noticeably bad quality — not usable for production. Trained primarily on English; Hebrew gutturals and phonemes don't map well. Small output files (~673 KB for 20s) confirm low visual quality.
- **[Sync Lipsync 1.9 & MuseTalk low quality]**: `fal-ai/sync-lipsync` (1.9.0-beta, $0.70/min) and `fal-ai/musetalk` (free) both produce small ~800 KB files for 20s clips — similar quality tier to LatentSync. Not viable replacements for VEED Fabric.
- **[Kling Avatar v2 Pro not worth 2x cost]**: `fal-ai/kling-video/ai-avatar/v2/pro` ($0.115/s) gives only a small quality bump over Standard ($0.0562/s). Not enough to justify the price. Neither version matches VEED Fabric's resolution/sharpness.
- **[OmniHuman v1.5 too slow for production]**: `fal-ai/bytedance/omnihuman/v1.5` ($0.16/s) — nice micro-expressions but unreliably slow. Timed out (10min+) on a 25s clip. Short clips (11s) worked but took 4-8 min. At 2x VEED's price with worse reliability, not worth it.
- **[Kling O1 has no lip-sync]**: Kling O1 (`fal-ai/kling-video/o1/...`) is for video generation/editing/style transfer only — no audio input, no lip-sync. For image+audio→talking head, use Kling Avatar v2 (`fal-ai/kling-video/ai-avatar/v2/standard`).
- **[Veo 3.1 not for talking heads]**: Google Veo 3.1 is text-to-video only — generates its own audio from prompts. Cannot feed it existing image + audio file. Not a VEED Fabric replacement despite having good lip-sync on self-generated speech.
- **[Qwen Max /edit doesn't lock faces]**: `fal-ai/qwen-image-max/edit` with reference image treats it as a style guide, NOT face-lock. Character drifts between scenes. Nano Banana Pro's reference support is much stronger.
- **[ElevenLabs multilingual_v2 + language_code]**: `eleven_multilingual_v2` does NOT support `language_code='he'` — returns 400 error. Don't pass `language_code` for this model; it auto-detects language from text. Only `eleven_v3` supports explicit language codes.
- **[Niqqud has limits for TTS]**: Adding Hebrew niqqud helps with some pronunciations but doesn't reliably fix all words. For tricky phrases (e.g. "משכו בדש"), sometimes it's better to just rewrite the line entirely rather than fighting pronunciation.
- **[ElevenLabs STS not for Hebrew]**: ElevenLabs Speech-to-Speech (`eleven_multilingual_sts_v2`) does NOT work for Hebrew — outputs identical audio regardless of voice_settings. Just passes through without converting. Use Chatterbox S2S instead.
- **[load_dotenv defeats `env -u` for testing]**: `env -u GOOGLE_API_KEY python scripts/foo.py` won't make the script see the key as missing if `foo.py` calls `load_dotenv()` — python-dotenv re-reads `.env` and re-populates `os.environ`. To genuinely test missing-key code paths, either rename `.env` temporarily or run from a directory without one. Burned $0.12 of Google quota learning this during a "no-API-call" dry run.
- **[Claude Code worktrees can hide newly-committed code]**: Desktop Claude Code's auto-isolation creates worktrees under `.claude/worktrees/<name>` on dedicated branches. Those branches don't auto-update from `master` — sessions reading from a stale worktree see code from whenever the worktree was created. Open Claude Code from the main repo dir (or `git merge master` inside the worktree) to see latest. Stale worktrees with no unique commits are safe to remove with `git worktree remove`.
- **[`os.environ[k] = v` from per-user UI on Streamlit Cloud]**: Process-global, leaks between concurrent users. User A pastes their key → user B (different browser session) opens the app → user B's pipeline reads `os.environ` and unknowingly spends user A's quota. Always use session_state + explicit-param pipeline functions.
- **[Streamlit `text_input` accepting both `value=` AND `key=`]**: Triggers warnings/errors about widget state being managed in two places. Use only `key=` and let session_state hold the value. Provide initial defaults via `st.session_state.setdefault(key, default)` BEFORE rendering the widget.
- **[Streamlit hides sidebar toggle on `layout="wide"` + `initial_sidebar_state="collapsed"`]**: The chevron isn't even in the DOM, no CSS can show it. Workaround: set `initial_sidebar_state="expanded"` so the settings drawer is visible from the start. Users can still close it via the X if they want canvas room.
- **[`st.toast(icon="✓")` rejects non-emoji symbols]**: Streamlit's emoji validator only accepts true emoji codepoints. Use `✅` not `✓`, `❌` not `✗`, `🗑️` (with VS16) not `🗑`. Verify with `streamlit.string_util.validate_emoji` before shipping.
- **[`load_dotenv()` defeats `env -u VAR` for testing]**: python-dotenv re-reads `.env` after the shell-level unset, so the Python process still sees the var. To genuinely test missing-key code paths, rename `.env` or run from a directory without one.
- **[AppTest `at.session_state.get(k)` doesn't work]**: `SafeSessionState` raises AttributeError on `.get`. Use `'k' in at.session_state` + bracket indexing. Same for `.keys()` — iterate via known keys instead.

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
- **[Lip-sync provider comparison (Feb 2026)]**: Tested 8 providers on fal.ai with Hebrew audio across photorealistic and puppet inputs. **VEED Fabric 1.0 is the winner** — best price/quality/speed balance. Aurora (Creatify) is a viable backup with nice hand movements but 2x slower and 25% more expensive. Full results below and in `output/lipsync_comparison/`. Script: `scripts/compare_lipsync.py`.
- **[Aurora (Creatify) as backup lip-sync]**: `fal-ai/creatify/aurora` ($0.10/s) produces good Hebrew lip-sync with natural hand/body movements. Claims 75+ language phoneme support. Quality comparable to VEED on puppets, but 2x slower (~210s vs ~100s for 25s clip) and 25% pricier. Keep as fallback if VEED has issues.
