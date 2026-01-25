"""Workflow 1: Image-based video generation pipeline."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import Config, get_config
from ..providers import FallbackProvider, ProviderError
from ..providers.audio import ElevenLabsProvider
from ..providers.image import NanoBananaProvider
from ..providers.video import VideoResolution
from ..providers.video.fal import VeedFabricFalProvider
from ..providers.video.replicate import VeedFabricReplicateProvider
from ..schemas import (
    ContentBrief,
    ImagePromptBatch,
    Script,
    ScriptRequest,
    SegmentList,
    VideoValidation,
)
from ..services import QualityValidator, ScenePlanner, ScriptGenerator, SubtitleGenerator
from ..utils import MetadataTracker, add_subtitles, concatenate_videos, extract_thumbnails

logger = logging.getLogger(__name__)


class Workflow1Pipeline:
    """Image-based video generation workflow.

    Flow:
    1. Generate script options (A/B testing)
    2. Select best script and segment
    3. Generate images for each segment
    4. Generate audio for each segment
    5. Generate video with lip-sync (VEED Fabric)
    6. Validate quality, remake if needed
    7. Add subtitles and concatenate
    8. Extract thumbnails and save metadata
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
        self._video_provider: Optional[FallbackProvider] = None

    async def initialize(self) -> None:
        """Initialize all services and providers."""
        if self._initialized:
            return

        logger.info("Initializing Workflow 1 pipeline...")

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

        fal_provider = VeedFabricFalProvider(
            api_key=self.config.api_keys.fal,
            resolution=resolution,
        )

        replicate_provider = VeedFabricReplicateProvider(
            api_key=self.config.api_keys.replicate,
            resolution=resolution,
        )

        self._video_provider = FallbackProvider(
            primary=fal_provider,
            fallback=replicate_provider,
        )

        self._initialized = True
        logger.info("Workflow 1 pipeline initialized")

    async def close(self) -> None:
        """Close all providers."""
        if self._audio_provider:
            await self._audio_provider.close()
        if self._image_provider:
            await self._image_provider.close()
        if self._video_provider:
            await self._video_provider.primary.close()
            await self._video_provider.fallback.close()
        self._initialized = False

    async def generate_script(
        self,
        request: ScriptRequest,
        auto_select: bool = True,
    ) -> Script:
        """Generate and segment a script.

        Args:
            request: Script generation request
            auto_select: Auto-select best option

        Returns:
            Complete Script with segments
        """
        await self.initialize()

        script = await self._script_generator.generate_script(
            request=request,
            auto_select=auto_select,
        )

        # Ensure scene variety
        script.segments = await self._scene_planner.ensure_scene_variety(
            script.segments
        )

        return script

    async def generate_images(
        self,
        segments: SegmentList,
        output_dir: Path,
    ) -> ImagePromptBatch:
        """Generate images for all segments.

        Args:
            segments: SegmentList with scene definitions
            output_dir: Directory to save images

        Returns:
            ImagePromptBatch with prompts and paths
        """
        await self.initialize()

        # Generate prompts
        prompts = await self._scene_planner.generate_image_prompts(segments)

        # Generate images
        for prompt in prompts.prompts:
            image_path = output_dir / f"segment_{prompt.segment_index:02d}_image.png"

            image_bytes, _ = await self._image_provider.generate_character_image(
                prompt=prompt.full_prompt,
                expression=prompt.expression.value,
                camera_angle=prompt.camera_angle.value,
                output_path=image_path,
            )

            # Update segment with image path
            segment = segments.get_segment(prompt.segment_index)
            if segment:
                segment.image_path = str(image_path)

            logger.info(f"Generated image for segment {prompt.segment_index}")

        return prompts

    async def generate_audio_for_segment(
        self,
        segment,
        output_dir: Path,
    ) -> tuple[bytes, float]:
        """Generate audio for a single segment.

        Args:
            segment: Segment to generate audio for
            output_dir: Directory to save audio

        Returns:
            Tuple of (audio_bytes, duration)
        """
        await self.initialize()

        audio_path = output_dir / f"segment_{segment.index:02d}_audio.mp3"

        audio_bytes, duration = await self._audio_provider.generate_speech(
            text=segment.text,
            output_path=audio_path,
        )

        segment.audio_path = str(audio_path)
        segment.audio_duration = duration

        logger.info(f"Generated audio for segment {segment.index}: {duration:.2f}s")

        return audio_bytes, duration

    async def generate_video_for_segment(
        self,
        segment,
        image_bytes: bytes,
        audio_bytes: bytes,
        output_dir: Path,
    ) -> tuple[bytes, dict]:
        """Generate video for a single segment.

        Args:
            segment: Segment to generate video for
            image_bytes: Image data
            audio_bytes: Audio data
            output_dir: Directory to save video

        Returns:
            Tuple of (video_bytes, metadata)
        """
        await self.initialize()

        video_path = output_dir / f"segment_{segment.index:02d}_video.mp4"

        result = await self._video_provider.execute(
            "generate_video",
            image=image_bytes,
            audio=audio_bytes,
            output_path=video_path,
        )

        if not result.success:
            raise result.error or ProviderError("Video generation failed", "workflow1")

        video_bytes, metadata = result.data

        segment.video_path = str(video_path)
        segment.video_duration = metadata.get("duration", segment.audio_duration)

        logger.info(f"Generated video for segment {segment.index}")

        return video_bytes, metadata

    async def process_segment(
        self,
        segment,
        output_dir: Path,
        metadata_tracker: MetadataTracker,
    ) -> bool:
        """Process a single segment: image, audio, video.

        Args:
            segment: Segment to process
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
                # Generate image if not exists
                prompt = await self._scene_planner.generate_image_prompts(
                    SegmentList(segments=[segment])
                )

                image_path = output_dir / f"segment_{segment.index:02d}_image.png"
                image_bytes, _ = await self._image_provider.generate_character_image(
                    prompt=prompt.prompts[0].full_prompt,
                    output_path=image_path,
                )
                segment.image_path = str(image_path)

            # Generate audio
            audio_bytes, audio_duration = await self.generate_audio_for_segment(
                segment, output_dir
            )

            # Track audio cost (~$0.30/min for ElevenLabs)
            metadata_tracker.add_cost(
                provider="elevenlabs",
                operation="tts",
                amount=audio_duration / 60 * 0.30,
                details={"duration": audio_duration, "segment": segment.index},
            )

            # Generate video
            video_bytes, video_metadata = await self.generate_video_for_segment(
                segment, image_bytes, audio_bytes, output_dir
            )

            # Track video cost (~$0.08/sec for VEED Fabric on Fal.ai)
            video_duration = video_metadata.get("duration", audio_duration)
            metadata_tracker.add_cost(
                provider=video_metadata.get("provider", "fal"),
                operation="video_generation",
                amount=video_duration * 0.08,
                details={"duration": video_duration, "segment": segment.index},
            )

            # Add segment metadata
            metadata_tracker.add_segment_metadata(
                index=segment.index,
                text=segment.text,
                duration=video_duration,
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
        output_dir: Path,
        metadata_tracker: MetadataTracker,
        max_remakes: int = 2,
    ) -> VideoValidation:
        """Validate segments and remake failures.

        Args:
            segments: Segments to validate
            output_dir: Output directory
            metadata_tracker: Metadata tracker
            max_remakes: Maximum remake attempts

        Returns:
            Final validation result
        """
        await self.initialize()

        for attempt in range(max_remakes + 1):
            validation = await self._quality_validator.validate_video(segments)

            if validation.overall_decision.value == "approve":
                logger.info("All segments passed validation")
                return validation

            if attempt >= max_remakes:
                logger.warning(
                    f"Max remake attempts reached. "
                    f"{validation.segments_needing_remake} segments still need work."
                )
                return validation

            # Remake failed segments
            segments_to_remake = validation.get_segments_to_remake()
            logger.info(f"Remaking {len(segments_to_remake)} segments (attempt {attempt + 1})")

            for segment_index in segments_to_remake:
                segment = segments.get_segment(segment_index)
                if segment:
                    success = await self.process_segment(
                        segment, output_dir, metadata_tracker
                    )
                    if not success:
                        logger.error(f"Failed to remake segment {segment_index}")

        return validation

    async def finalize_video(
        self,
        segments: SegmentList,
        output_dir: Path,
        metadata_tracker: MetadataTracker,
    ) -> Path:
        """Concatenate segments, add subtitles, extract thumbnails.

        Args:
            segments: Processed segments
            output_dir: Output directory
            metadata_tracker: Metadata tracker

        Returns:
            Path to final video
        """
        # Get video paths
        video_paths = [
            Path(s.video_path)
            for s in sorted(segments.segments, key=lambda x: x.index)
            if s.video_path
        ]

        if not video_paths:
            raise ValueError("No video segments to concatenate")

        # Concatenate videos
        concatenated_path = output_dir / "video_raw.mp4"
        await concatenate_videos(
            video_paths=video_paths,
            output_path=concatenated_path,
            transition="fade",
            transition_duration=0.3,
        )

        # Generate subtitles
        subtitle_path = output_dir / "subtitles.srt"
        self._subtitle_generator.generate_srt(
            segments=segments,
            output_path=subtitle_path,
        )

        # Add subtitles to video
        final_path = output_dir / "video.mp4"
        await add_subtitles(
            video_path=concatenated_path,
            subtitle_path=subtitle_path,
            output_path=final_path,
            burn_in=True,
        )

        # Extract thumbnails
        thumbnail_dir = output_dir / "thumbnails"
        thumbnails = await extract_thumbnails(
            video_path=final_path,
            output_dir=thumbnail_dir,
            count=2,
        )

        # Update metadata
        metadata_tracker.set_output_files(
            video_path=final_path,
            subtitle_path=subtitle_path,
            thumbnail_paths=thumbnails,
        )

        logger.info(f"Finalized video: {final_path}")

        return final_path

    async def run(
        self,
        topic: Optional[str] = None,
        angle: Optional[str] = None,
        brief: Optional[ContentBrief] = None,
        output_dir: Optional[Path] = None,
        preview: bool = False,
        reference_image: Optional[Path] = None,
    ) -> Path:
        """Run the complete Workflow 1 pipeline.

        Args:
            topic: Video topic (not needed if brief provided)
            angle: Video angle/guidelines (not needed if brief provided)
            brief: Detailed content brief (recommended for quality output)
            output_dir: Output directory (auto-generated if not specified)
            preview: Generate preview (fewer segments)
            reference_image: Optional reference image path

        Returns:
            Path to final video
        """
        await self.initialize()

        # Validate input
        if brief is None and (topic is None or angle is None):
            raise ValueError("Must provide either (topic + angle) or brief")

        # Derive topic/angle from brief if not provided
        if brief:
            topic = topic or brief.title
            angle = angle or f"{brief.emotional_tone}, {', '.join(brief.rhetorical_devices)}"

        # Setup output directory
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = "".join(c for c in topic[:30] if c.isalnum() or c in " -_").strip()
            safe_topic = safe_topic.replace(" ", "_")
            output_dir = self.config.output_dir / f"{safe_topic}_{timestamp}"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize metadata tracker
        metadata = MetadataTracker(output_dir)
        metadata.set_topic(topic, angle)
        if brief:
            metadata._metadata["brief"] = brief.model_dump(exclude_none=True)

        try:
            # Step 1: Generate script
            logger.info("Step 1: Generating script...")
            request = ScriptRequest(
                topic=topic,
                angle=angle,
                brief=brief,
                target_duration=60.0,
                min_segments=self.config.pipeline.preview_segments if preview else self.config.pipeline.segments_min,
                max_segments=self.config.pipeline.preview_segments if preview else self.config.pipeline.segments_max,
                reference_image_path=str(reference_image) if reference_image else None,
            )

            script = await self.generate_script(request)

            # Record A/B testing (if we have options data)
            if hasattr(script, "selected_option"):
                metadata.record_ab_testing(
                    options=[{"option_id": script.selected_option.option_id,
                              "title": script.selected_option.title,
                              "tone": script.selected_option.tone.value,
                              "summary": script.selected_option.summary}],
                    selected_option=script.selected_option.option_id,
                    selection_reasoning=script.selection_reasoning or "Auto-selected",
                )

            # Step 2: Generate images
            logger.info("Step 2: Generating images...")
            await self.generate_images(script.segments, output_dir)

            # Step 3: Process each segment (audio + video)
            logger.info("Step 3: Processing segments...")
            for segment in script.segments.segments:
                success = await self.process_segment(segment, output_dir, metadata)
                if not success:
                    logger.warning(f"Segment {segment.index} failed, will retry in validation")

            # Step 4: Validate and remake
            logger.info("Step 4: Validating and remaking if needed...")
            validation = await self.validate_and_remake(
                script.segments,
                output_dir,
                metadata,
                max_remakes=self.config.pipeline.max_remake_attempts,
            )

            # Step 5: Finalize video
            logger.info("Step 5: Finalizing video...")
            final_path = await self.finalize_video(script.segments, output_dir, metadata)

            # Finalize metadata
            from ..utils.ffmpeg import get_video_info
            video_info = await get_video_info(final_path)

            metadata.finalize(
                success=True,
                final_video_path=final_path,
                total_duration=video_info.get("duration"),
            )
            metadata.save()

            logger.info(f"Workflow 1 complete! Output: {final_path}")
            logger.info(f"Total cost: ${metadata.get_total_cost():.2f}")

            return final_path

        except Exception as e:
            logger.error(f"Workflow 1 failed: {e}")
            metadata.set_status("failed", str(e))
            metadata.finalize(success=False)
            metadata.save()
            raise

        finally:
            await self.close()
