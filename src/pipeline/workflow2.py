"""Workflow 2: Video-based generation pipeline with separate lip-sync."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import Config, get_config
from ..providers import FallbackProvider, ProviderError
from ..providers.audio import ElevenLabsProvider
from ..providers.image import NanoBananaProvider
from ..providers.video import VideoResolution
from ..providers.video.fal import KlingFalProvider, SyncLipsyncFalProvider
from ..providers.video.replicate import KlingReplicateProvider, SyncLipsyncReplicateProvider
from ..schemas import (
    ImagePromptBatch,
    MotionPromptBatch,
    Script,
    ScriptRequest,
    SegmentList,
)
from ..services import QualityValidator, ScenePlanner, ScriptGenerator, SubtitleGenerator
from ..utils import MetadataTracker, add_subtitles, concatenate_videos, extract_thumbnails

logger = logging.getLogger(__name__)


class Workflow2Pipeline:
    """Video-based generation workflow with separate lip-sync.

    Flow:
    1. Generate script options (A/B testing)
    2. Select best script and segment
    3. Generate images for each segment
    4. Generate audio for each segment
    5. Generate video with motion (Kling - no audio)
    6. Add lip-sync to video (sync lipsync-2-pro)
    7. Validate quality, remake if needed
    8. Add subtitles and concatenate
    9. Extract thumbnails and save metadata

    This workflow produces higher quality motion but costs ~40% more.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
    ):
        self.config = config or get_config()
        self._initialized = False

        # Services
        self._script_generator: Optional[ScriptGenerator] = None
        self._scene_planner: Optional[ScenePlanner] = None
        self._quality_validator: Optional[QualityValidator] = None
        self._subtitle_generator: Optional[SubtitleGenerator] = None

        # Providers
        self._audio_provider: Optional[ElevenLabsProvider] = None
        self._image_provider: Optional[NanoBananaProvider] = None
        self._kling_provider: Optional[FallbackProvider] = None
        self._sync_provider: Optional[FallbackProvider] = None

    async def initialize(self) -> None:
        """Initialize all services and providers."""
        if self._initialized:
            return

        logger.info("Initializing Workflow 2 pipeline...")

        # Initialize services
        self._script_generator = ScriptGenerator(self.config)
        self._scene_planner = ScenePlanner(self.config)
        self._quality_validator = QualityValidator(self.config)
        self._subtitle_generator = SubtitleGenerator(self.config)

        # Initialize providers
        self._audio_provider = ElevenLabsProvider(
            api_key=self.config.api_keys.elevenlabs,
            voice_id=self.config.audio.voice_id,
            model_id=self.config.audio.model_id,
        )

        self._image_provider = NanoBananaProvider(
            api_key=self.config.api_keys.google,
            model=self.config.image.model,
            aspect_ratio=self.config.image.aspect_ratio,
        )

        resolution = VideoResolution(self.config.video.resolution)

        # Kling provider (image -> video with motion)
        kling_fal = KlingFalProvider(
            api_key=self.config.api_keys.fal,
            resolution=resolution,
        )
        kling_replicate = KlingReplicateProvider(
            api_key=self.config.api_keys.replicate,
            resolution=resolution,
        )
        self._kling_provider = FallbackProvider(
            primary=kling_fal,
            fallback=kling_replicate,
        )

        # Sync lipsync provider (video + audio -> video with lip-sync)
        sync_fal = SyncLipsyncFalProvider(
            api_key=self.config.api_keys.fal,
            resolution=resolution,
        )
        sync_replicate = SyncLipsyncReplicateProvider(
            api_key=self.config.api_keys.replicate,
            resolution=resolution,
        )
        self._sync_provider = FallbackProvider(
            primary=sync_fal,
            fallback=sync_replicate,
        )

        self._initialized = True
        logger.info("Workflow 2 pipeline initialized")

    async def close(self) -> None:
        """Close all providers."""
        if self._audio_provider:
            await self._audio_provider.close()
        if self._image_provider:
            await self._image_provider.close()
        if self._kling_provider:
            await self._kling_provider.primary.close()
            await self._kling_provider.fallback.close()
        if self._sync_provider:
            await self._sync_provider.primary.close()
            await self._sync_provider.fallback.close()
        self._initialized = False

    async def generate_script(
        self,
        request: ScriptRequest,
        auto_select: bool = True,
    ) -> Script:
        """Generate and segment a script."""
        await self.initialize()

        script = await self._script_generator.generate_script(
            request=request,
            auto_select=auto_select,
        )

        script.segments = await self._scene_planner.ensure_scene_variety(
            script.segments
        )

        return script

    async def generate_images(
        self,
        segments: SegmentList,
        output_dir: Path,
    ) -> ImagePromptBatch:
        """Generate images for all segments."""
        await self.initialize()

        prompts = await self._scene_planner.generate_image_prompts(segments)

        for prompt in prompts.prompts:
            image_path = output_dir / f"segment_{prompt.segment_index:02d}_image.png"

            await self._image_provider.generate_character_image(
                prompt=prompt.full_prompt,
                expression=prompt.expression.value,
                camera_angle=prompt.camera_angle.value,
                output_path=image_path,
            )

            segment = segments.get_segment(prompt.segment_index)
            if segment:
                segment.image_path = str(image_path)

            logger.info(f"Generated image for segment {prompt.segment_index}")

        return prompts

    async def generate_motion_prompts(
        self,
        segments: SegmentList,
    ) -> MotionPromptBatch:
        """Generate motion prompts for Kling video generation."""
        await self.initialize()

        return await self._scene_planner.generate_motion_prompts(segments)

    async def process_segment(
        self,
        segment,
        motion_prompt: str,
        output_dir: Path,
        metadata_tracker: MetadataTracker,
    ) -> bool:
        """Process a single segment: image, audio, Kling video, sync lip-sync.

        Args:
            segment: Segment to process
            motion_prompt: Motion description for Kling
            output_dir: Output directory
            metadata_tracker: Metadata tracker

        Returns:
            True if successful
        """
        try:
            # Load image
            if segment.image_path:
                image_bytes = Path(segment.image_path).read_bytes()
            else:
                raise ProviderError(f"No image for segment {segment.index}", "workflow2")

            # Generate audio
            audio_path = output_dir / f"segment_{segment.index:02d}_audio.mp3"
            audio_bytes, audio_duration = await self._audio_provider.generate_speech(
                text=segment.text,
                output_path=audio_path,
            )
            segment.audio_path = str(audio_path)
            segment.audio_duration = audio_duration

            metadata_tracker.add_cost(
                provider="elevenlabs",
                operation="tts",
                amount=audio_duration / 60 * 0.30,
                details={"duration": audio_duration, "segment": segment.index},
            )

            logger.info(f"Generated audio for segment {segment.index}: {audio_duration:.2f}s")

            # Generate video with motion (Kling - no audio)
            kling_path = output_dir / f"segment_{segment.index:02d}_kling.mp4"

            kling_result = await self._kling_provider.execute(
                "generate_video",
                image=image_bytes,
                motion_prompt=motion_prompt,
                duration=min(audio_duration + 1, 10),  # Kling max 10s
                output_path=kling_path,
            )

            if not kling_result.success:
                raise kling_result.error or ProviderError("Kling failed", "workflow2")

            kling_bytes, kling_metadata = kling_result.data

            metadata_tracker.add_cost(
                provider=kling_metadata.get("provider", "fal"),
                operation="kling_video",
                amount=min(audio_duration, 10) * 0.07,  # ~$0.07/sec
                details={"duration": audio_duration, "segment": segment.index},
            )

            logger.info(f"Generated Kling video for segment {segment.index}")

            # Add lip-sync (sync lipsync-2-pro)
            video_path = output_dir / f"segment_{segment.index:02d}_video.mp4"

            sync_result = await self._sync_provider.execute(
                "add_lipsync",
                video=kling_bytes,
                audio=audio_bytes,
                output_path=video_path,
            )

            if not sync_result.success:
                raise sync_result.error or ProviderError("Sync failed", "workflow2")

            video_bytes, sync_metadata = sync_result.data

            metadata_tracker.add_cost(
                provider=sync_metadata.get("provider", "fal"),
                operation="sync_lipsync",
                amount=audio_duration * 0.05,  # ~$0.05/sec for sync
                details={"duration": audio_duration, "segment": segment.index},
            )

            segment.video_path = str(video_path)
            segment.video_duration = sync_metadata.get("duration", audio_duration)

            logger.info(f"Added lip-sync for segment {segment.index}")

            metadata_tracker.add_segment_metadata(
                index=segment.index,
                text=segment.text,
                duration=segment.video_duration,
                audio_path=segment.audio_path,
                video_path=segment.video_path,
                image_path=segment.image_path,
            )

            return True

        except Exception as e:
            logger.error(f"Error processing segment {segment.index}: {e}")
            metadata_tracker.record_error(
                error_type="segment_processing",
                message=str(e),
                recoverable=True,
                context={"segment_index": segment.index},
            )
            return False

    async def validate_and_remake(
        self,
        segments: SegmentList,
        motion_prompts: MotionPromptBatch,
        output_dir: Path,
        metadata_tracker: MetadataTracker,
        max_remakes: int = 2,
    ):
        """Validate segments and remake failures."""
        await self.initialize()

        for attempt in range(max_remakes + 1):
            validation = await self._quality_validator.validate_video(segments)

            if validation.overall_decision.value == "approve":
                logger.info("All segments passed validation")
                return validation

            if attempt >= max_remakes:
                logger.warning(f"Max remake attempts reached")
                return validation

            segments_to_remake = validation.get_segments_to_remake()
            logger.info(f"Remaking {len(segments_to_remake)} segments (attempt {attempt + 1})")

            for segment_index in segments_to_remake:
                segment = segments.get_segment(segment_index)
                motion_prompt = motion_prompts.get_prompt(segment_index)

                if segment and motion_prompt:
                    await self.process_segment(
                        segment,
                        motion_prompt.motion_description,
                        output_dir,
                        metadata_tracker,
                    )

        return validation

    async def finalize_video(
        self,
        segments: SegmentList,
        output_dir: Path,
        metadata_tracker: MetadataTracker,
    ) -> Path:
        """Concatenate segments, add subtitles, extract thumbnails."""
        video_paths = [
            Path(s.video_path)
            for s in sorted(segments.segments, key=lambda x: x.index)
            if s.video_path
        ]

        if not video_paths:
            raise ValueError("No video segments to concatenate")

        concatenated_path = output_dir / "video_raw.mp4"
        await concatenate_videos(
            video_paths=video_paths,
            output_path=concatenated_path,
            transition="fade",
            transition_duration=0.3,
        )

        subtitle_path = output_dir / "subtitles.srt"
        self._subtitle_generator.generate_srt(
            segments=segments,
            output_path=subtitle_path,
        )

        final_path = output_dir / "video.mp4"
        await add_subtitles(
            video_path=concatenated_path,
            subtitle_path=subtitle_path,
            output_path=final_path,
            burn_in=True,
        )

        thumbnail_dir = output_dir / "thumbnails"
        thumbnails = await extract_thumbnails(
            video_path=final_path,
            output_dir=thumbnail_dir,
            count=2,
        )

        metadata_tracker.set_output_files(
            video_path=final_path,
            subtitle_path=subtitle_path,
            thumbnail_paths=thumbnails,
        )

        logger.info(f"Finalized video: {final_path}")

        return final_path

    async def run(
        self,
        topic: str,
        angle: str,
        output_dir: Optional[Path] = None,
        preview: bool = False,
        reference_image: Optional[Path] = None,
    ) -> Path:
        """Run the complete Workflow 2 pipeline.

        Args:
            topic: Video topic
            angle: Video angle/guidelines
            output_dir: Output directory
            preview: Generate preview (fewer segments)
            reference_image: Optional reference image path

        Returns:
            Path to final video
        """
        await self.initialize()

        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = "".join(c for c in topic[:30] if c.isalnum() or c in " -_").strip()
            safe_topic = safe_topic.replace(" ", "_")
            output_dir = self.config.output_dir / f"{safe_topic}_{timestamp}_wf2"

        output_dir.mkdir(parents=True, exist_ok=True)

        metadata = MetadataTracker(output_dir)
        metadata.set_topic(topic, angle)
        metadata._metadata["workflow"] = 2

        try:
            # Step 1: Generate script
            logger.info("Step 1: Generating script...")
            request = ScriptRequest(
                topic=topic,
                angle=angle,
                target_duration=60.0,
                min_segments=self.config.pipeline.preview_segments if preview else self.config.pipeline.segments_min,
                max_segments=self.config.pipeline.preview_segments if preview else self.config.pipeline.segments_max,
                reference_image_path=str(reference_image) if reference_image else None,
            )

            script = await self.generate_script(request)

            # Step 2: Generate images
            logger.info("Step 2: Generating images...")
            await self.generate_images(script.segments, output_dir)

            # Step 3: Generate motion prompts
            logger.info("Step 3: Generating motion prompts...")
            motion_prompts = await self.generate_motion_prompts(script.segments)

            # Step 4: Process each segment (audio + Kling + sync)
            logger.info("Step 4: Processing segments...")
            for segment in script.segments.segments:
                motion_prompt = motion_prompts.get_prompt(segment.index)
                motion_desc = motion_prompt.motion_description if motion_prompt else "subtle natural movement"

                await self.process_segment(segment, motion_desc, output_dir, metadata)

            # Step 5: Validate and remake
            logger.info("Step 5: Validating and remaking if needed...")
            await self.validate_and_remake(
                script.segments,
                motion_prompts,
                output_dir,
                metadata,
                max_remakes=self.config.pipeline.max_remake_attempts,
            )

            # Step 6: Finalize video
            logger.info("Step 6: Finalizing video...")
            final_path = await self.finalize_video(script.segments, output_dir, metadata)

            from ..utils.ffmpeg import get_video_info
            video_info = await get_video_info(final_path)

            metadata.finalize(
                success=True,
                final_video_path=final_path,
                total_duration=video_info.get("duration"),
            )
            metadata.save()

            logger.info(f"Workflow 2 complete! Output: {final_path}")
            logger.info(f"Total cost: ${metadata.get_total_cost():.2f}")

            return final_path

        except Exception as e:
            logger.error(f"Workflow 2 failed: {e}")
            metadata.set_status("failed", str(e))
            metadata.finalize(success=False)
            metadata.save()
            raise

        finally:
            await self.close()
