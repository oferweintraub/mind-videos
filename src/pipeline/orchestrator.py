"""Pipeline orchestrator for video generation."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import Config, get_config
from ..providers import FallbackProvider, ProviderError, ProviderResult
from ..providers.audio import ElevenLabsProvider
from ..providers.video import VideoResolution
from ..providers.video.fal import VeedFabricFalProvider
from ..providers.video.replicate import VeedFabricReplicateProvider
from ..schemas import Segment

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result from pipeline execution."""

    success: bool
    video_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SegmentResult:
    """Result from processing a single segment."""

    segment: Segment
    audio_bytes: Optional[bytes] = None
    audio_duration: Optional[float] = None
    video_bytes: Optional[bytes] = None
    video_duration: Optional[float] = None
    error: Optional[str] = None


class PipelineOrchestrator:
    """Orchestrates the video generation pipeline.

    Coordinates between audio, image, and video providers
    to generate complete video segments.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
    ):
        self.config = config or get_config()
        self._audio_provider: Optional[ElevenLabsProvider] = None
        self._video_provider: Optional[FallbackProvider] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all providers."""
        if self._initialized:
            return

        logger.info("Initializing pipeline providers...")

        # Initialize audio provider
        self._audio_provider = ElevenLabsProvider(
            api_key=self.config.api_keys.elevenlabs,
            voice_id=self.config.audio.voice_id,
            model_id=self.config.audio.model_id,
            language_code=self.config.audio.language_code,
            stability=self.config.audio.stability,
            similarity_boost=self.config.audio.similarity_boost,
        )

        # Initialize video providers with fallback
        resolution = VideoResolution(self.config.video.resolution)

        fal_provider = VeedFabricFalProvider(
            api_key=self.config.api_keys.fal,
            model_id=self.config.video.veed_model,
            resolution=resolution,
            poll_interval=self.config.video.poll_interval,
            max_poll_time=self.config.video.timeout,
        )

        replicate_provider = VeedFabricReplicateProvider(
            api_key=self.config.api_keys.replicate,
            model_id=self.config.video.veed_replicate_model,
            resolution=resolution,
            poll_interval=self.config.video.poll_interval,
            max_poll_time=self.config.video.timeout,
        )

        self._video_provider = FallbackProvider(
            primary=fal_provider,
            fallback=replicate_provider,
        )

        self._initialized = True
        logger.info("Pipeline providers initialized")

    async def close(self) -> None:
        """Close all providers and cleanup resources."""
        if self._audio_provider:
            await self._audio_provider.close()

        if self._video_provider:
            await self._video_provider.primary.close()
            await self._video_provider.fallback.close()

        self._initialized = False

    async def generate_audio(
        self,
        text: str,
        output_path: Optional[Path] = None,
    ) -> tuple[bytes, float]:
        """Generate audio from text.

        Args:
            text: Hebrew text to convert to speech
            output_path: Optional path to save audio

        Returns:
            Tuple of (audio_bytes, duration_seconds)
        """
        if not self._initialized:
            await self.initialize()

        audio_bytes, duration = await self._audio_provider.generate_speech(
            text=text,
            output_path=output_path,
        )

        return audio_bytes, duration

    async def generate_video(
        self,
        image: bytes,
        audio: bytes,
        output_path: Optional[Path] = None,
    ) -> tuple[bytes, dict]:
        """Generate video from image and audio.

        Args:
            image: Input image bytes
            audio: Audio bytes for lip-sync
            output_path: Optional path to save video

        Returns:
            Tuple of (video_bytes, metadata_dict)
        """
        if not self._initialized:
            await self.initialize()

        result = await self._video_provider.execute(
            "generate_video",
            image=image,
            audio=audio,
            output_path=output_path,
        )

        if not result.success:
            raise result.error or ProviderError(
                "Video generation failed",
                "pipeline",
            )

        return result.data

    async def process_segment(
        self,
        segment: Segment,
        image: bytes,
        output_dir: Path,
    ) -> SegmentResult:
        """Process a single segment.

        Args:
            segment: Segment to process
            image: Image bytes for the segment
            output_dir: Directory to save outputs

        Returns:
            SegmentResult with paths and metadata
        """
        if not self._initialized:
            await self.initialize()

        output_dir.mkdir(parents=True, exist_ok=True)
        result = SegmentResult(segment=segment)

        try:
            # Generate audio
            audio_path = output_dir / f"segment_{segment.index:02d}_audio.mp3"
            logger.info(f"Generating audio for segment {segment.index}...")

            audio_bytes, audio_duration = await self.generate_audio(
                text=segment.text,
                output_path=audio_path,
            )

            result.audio_bytes = audio_bytes
            result.audio_duration = audio_duration
            segment.audio_path = str(audio_path)
            segment.audio_duration = audio_duration

            logger.info(
                f"Audio generated for segment {segment.index}: {audio_duration:.2f}s"
            )

            # Generate video
            video_path = output_dir / f"segment_{segment.index:02d}_video.mp4"
            logger.info(f"Generating video for segment {segment.index}...")

            video_bytes, video_metadata = await self.generate_video(
                image=image,
                audio=audio_bytes,
                output_path=video_path,
            )

            result.video_bytes = video_bytes
            result.video_duration = video_metadata.get("duration") or audio_duration
            segment.video_path = str(video_path)
            segment.video_duration = result.video_duration

            duration_str = f"{result.video_duration:.2f}s" if result.video_duration else "unknown"
            logger.info(
                f"Video generated for segment {segment.index}: {duration_str}"
            )

        except Exception as e:
            result.error = str(e)
            logger.error(f"Error processing segment {segment.index}: {e}")

        return result

    async def test_single_segment(
        self,
        text: str,
        image_path: Path,
        output_dir: Optional[Path] = None,
    ) -> PipelineResult:
        """Test pipeline with a single text/image pair.

        Args:
            text: Hebrew text to convert to speech
            image_path: Path to input image
            output_dir: Directory for outputs (defaults to config output_dir)

        Returns:
            PipelineResult with paths and metadata
        """
        if not self._initialized:
            await self.initialize()

        # Setup output directory
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = self.config.output_dir / f"test_{timestamp}"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Create a test segment
        from ..schemas.segment import (
            CameraAngle,
            Expression,
            Lighting,
            SceneDefinition,
        )

        segment = Segment(
            index=0,
            text=text,
            duration_estimate=8.0,
            scene=SceneDefinition(
                camera_angle=CameraAngle.MEDIUM,
                lighting=Lighting.NATURAL,
                expression=Expression.NEUTRAL,
                setting="Indoor setting",
            ),
            purpose="Test segment",
        )

        # Load image
        if not image_path.exists():
            return PipelineResult(
                success=False,
                error=f"Image not found: {image_path}",
            )

        image_bytes = image_path.read_bytes()

        # Process segment
        result = await self.process_segment(
            segment=segment,
            image=image_bytes,
            output_dir=output_dir,
        )

        if result.error:
            return PipelineResult(
                success=False,
                error=result.error,
            )

        return PipelineResult(
            success=True,
            video_path=Path(segment.video_path) if segment.video_path else None,
            audio_path=Path(segment.audio_path) if segment.audio_path else None,
            duration=result.video_duration,
            metadata={
                "audio_duration": result.audio_duration,
                "video_duration": result.video_duration,
                "text": text,
                "output_dir": str(output_dir),
            },
        )


async def run_test(
    text: str,
    image_path: Path,
    output_dir: Optional[Path] = None,
) -> PipelineResult:
    """Convenience function to run a single test.

    Args:
        text: Hebrew text to convert to speech
        image_path: Path to input image
        output_dir: Optional output directory

    Returns:
        PipelineResult
    """
    orchestrator = PipelineOrchestrator()

    try:
        return await orchestrator.test_single_segment(
            text=text,
            image_path=image_path,
            output_dir=output_dir,
        )
    finally:
        await orchestrator.close()
