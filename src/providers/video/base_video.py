"""Extended base class for video providers."""

import asyncio
import logging
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from ..base import BaseVideoProvider, ProviderError, ProviderResult, RetryConfig

logger = logging.getLogger(__name__)


class VideoResolution(str, Enum):
    """Supported video resolutions."""

    RES_480P = "480p"
    RES_720P = "720p"
    RES_1080P = "1080p"


class VideoStatus(str, Enum):
    """Video generation job status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class VideoJobResult:
    """Result from a video generation job."""

    job_id: str
    status: VideoStatus
    video_url: Optional[str] = None
    video_bytes: Optional[bytes] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ExtendedVideoProvider(BaseVideoProvider):
    """Extended base class with polling and job management."""

    def __init__(
        self,
        name: str,
        api_key: str,
        model_id: str,
        resolution: VideoResolution = VideoResolution.RES_480P,
        poll_interval: int = 5,
        max_poll_time: int = 300,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 60.0,
    ):
        super().__init__(
            name=name,
            api_key=api_key,
            retry_config=retry_config,
            timeout=timeout,
        )
        self.model_id = model_id
        self.resolution = resolution
        self.poll_interval = poll_interval
        self.max_poll_time = max_poll_time

    @abstractmethod
    async def _submit_job(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs,
    ) -> str:
        """Submit a video generation job.

        Returns:
            Job ID for tracking
        """
        pass

    @abstractmethod
    async def _check_job_status(self, job_id: str) -> VideoJobResult:
        """Check status of a video generation job."""
        pass

    @abstractmethod
    async def _download_video(self, video_url: str) -> bytes:
        """Download video from URL."""
        pass

    async def _poll_until_complete(
        self,
        job_id: str,
        operation_name: str = "video_generation",
    ) -> VideoJobResult:
        """Poll for job completion with timeout."""
        import time

        start_time = time.time()
        last_status = None

        while time.time() - start_time < self.max_poll_time:
            try:
                result = await self._check_job_status(job_id)

                if result.status != last_status:
                    logger.info(
                        f"{self.name}: Job {job_id} status: {result.status.value}"
                    )
                    last_status = result.status

                if result.status == VideoStatus.COMPLETED:
                    return result

                if result.status == VideoStatus.FAILED:
                    raise ProviderError(
                        f"Video generation failed: {result.error_message}",
                        self.name,
                    )

                await asyncio.sleep(self.poll_interval)

            except ProviderError:
                raise
            except Exception as e:
                logger.warning(f"{self.name}: Error polling job {job_id}: {e}")
                await asyncio.sleep(self.poll_interval)

        raise ProviderError(
            f"Video generation timed out after {self.max_poll_time}s",
            self.name,
        )

    async def generate_video(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Generate a video from an image.

        Args:
            image: Input image bytes
            audio: Optional audio for lip-sync
            motion_prompt: Optional motion description
            duration: Target duration in seconds
            output_path: Optional path to save video
            **kwargs: Additional provider-specific parameters

        Returns:
            Tuple of (video_bytes, metadata_dict)
        """
        # Submit job
        async def _submit():
            return await self._submit_job(
                image=image,
                audio=audio,
                motion_prompt=motion_prompt,
                duration=duration,
                **kwargs,
            )

        submit_result = await self._retry_operation(_submit, "submit_video_job")

        if not submit_result.success:
            raise submit_result.error or ProviderError(
                "Failed to submit video job",
                self.name,
            )

        job_id = submit_result.data
        logger.info(f"{self.name}: Submitted video job {job_id}")

        # Poll for completion
        job_result = await self._poll_until_complete(job_id)

        # Download video if we got a URL
        if job_result.video_url and not job_result.video_bytes:
            async def _download():
                return await self._download_video(job_result.video_url)

            download_result = await self._retry_operation(_download, "download_video")

            if not download_result.success:
                raise download_result.error or ProviderError(
                    "Failed to download video",
                    self.name,
                )

            video_bytes = download_result.data
        else:
            video_bytes = job_result.video_bytes

        if video_bytes is None:
            raise ProviderError("No video data received", self.name)

        # Save to file if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_bytes)
            logger.info(f"Video saved to {output_path}")

        metadata = {
            "job_id": job_id,
            "duration": job_result.duration,
            "resolution": self.resolution.value,
            "model_id": self.model_id,
            "provider": self.name,
            **job_result.metadata,
        }

        return video_bytes, metadata

    async def add_lipsync(
        self,
        video: bytes,
        audio: bytes,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Add lip-sync to an existing video.

        Default implementation raises NotImplementedError.
        Override in providers that support this feature.
        """
        raise NotImplementedError(
            f"{self.name} does not support adding lip-sync to existing videos"
        )

    async def generate_video_with_result(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> ProviderResult[tuple[bytes, dict]]:
        """Generate video and return full result with metadata."""
        async def _generate():
            return await self.generate_video(
                image=image,
                audio=audio,
                motion_prompt=motion_prompt,
                duration=duration,
                output_path=output_path,
                **kwargs,
            )

        return await self._retry_operation(_generate, "generate_video")
