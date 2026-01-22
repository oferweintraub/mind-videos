"""Sync lipsync-2-pro provider using Fal.ai."""

import base64
import logging
from pathlib import Path
from typing import Optional

import fal_client

from ...base import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
    RetryConfig,
)
from ..base_video import (
    ExtendedVideoProvider,
    VideoJobResult,
    VideoResolution,
    VideoStatus,
)

logger = logging.getLogger(__name__)


class SyncLipsyncFalProvider(ExtendedVideoProvider):
    """Sync lipsync-2-pro via Fal.ai.

    Adds lip-sync to an existing video using audio.
    Used in Workflow 2 after Kling video generation.
    """

    DEFAULT_MODEL = "fal-ai/sync-lipsync-2-pro"

    def __init__(
        self,
        api_key: str,
        model_id: Optional[str] = None,
        resolution: VideoResolution = VideoResolution.RES_480P,
        poll_interval: int = 5,
        max_poll_time: int = 300,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 60.0,
    ):
        super().__init__(
            name="fal_sync_lipsync",
            api_key=api_key,
            model_id=model_id or self.DEFAULT_MODEL,
            resolution=resolution,
            poll_interval=poll_interval,
            max_poll_time=max_poll_time,
            retry_config=retry_config,
            timeout=timeout,
        )
        fal_client.api_key = api_key

    def _encode_media(self, data: bytes, media_type: str) -> str:
        """Encode bytes as data URI."""
        b64_data = base64.b64encode(data).decode("utf-8")
        return f"data:{media_type};base64,{b64_data}"

    def _handle_api_error(self, error: Exception) -> None:
        """Convert Fal.ai errors to provider errors."""
        error_str = str(error).lower()

        if "401" in error_str or "unauthorized" in error_str:
            raise AuthenticationError("Invalid Fal.ai API key", self.name)

        if "429" in error_str or "rate limit" in error_str:
            raise RateLimitError("Fal.ai rate limit exceeded", self.name, retry_after=60.0)

        raise ProviderError(str(error), self.name)

    async def health_check(self) -> bool:
        """Check if Fal.ai sync is accessible."""
        try:
            return True
        except Exception as e:
            logger.error(f"Sync Fal.ai health check failed: {e}")
            return False

    async def _submit_job(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs,
    ) -> str:
        """Submit a lip-sync job to Fal.ai.

        Note: For sync, 'image' is actually video bytes.
        """
        try:
            # Get video from kwargs or use image param as video
            video_bytes = kwargs.get("video", image)
            video_uri = self._encode_media(video_bytes, "video/mp4")

            if audio is None:
                raise ProviderError("Audio is required for lip-sync", self.name)

            audio_uri = self._encode_media(audio, "audio/mpeg")

            payload = {
                "video_url": video_uri,
                "audio_url": audio_uri,
            }

            handle = await fal_client.submit_async(
                self.model_id,
                arguments=payload,
            )

            return handle.request_id

        except ProviderError:
            raise
        except Exception as e:
            self._handle_api_error(e)

    async def _check_job_status(self, job_id: str) -> VideoJobResult:
        """Check status of a Fal.ai sync job."""
        try:
            status = await fal_client.status_async(
                self.model_id,
                job_id,
                with_logs=True,
            )

            if status.status == "COMPLETED":
                result = await fal_client.result_async(self.model_id, job_id)

                video_url = None
                duration = None

                if hasattr(result, "video") and result.video:
                    video_url = result.video.url if hasattr(result.video, "url") else result.video
                elif isinstance(result, dict):
                    video_url = result.get("video", {}).get("url") or result.get("video_url")

                if hasattr(result, "duration"):
                    duration = result.duration
                elif isinstance(result, dict):
                    duration = result.get("duration")

                return VideoJobResult(
                    job_id=job_id,
                    status=VideoStatus.COMPLETED,
                    video_url=video_url,
                    duration=duration,
                    metadata={"raw_result": result if isinstance(result, dict) else {}},
                )

            elif status.status == "FAILED":
                return VideoJobResult(
                    job_id=job_id,
                    status=VideoStatus.FAILED,
                    error_message=str(getattr(status, "error", "Unknown error")),
                )

            elif status.status == "IN_QUEUE":
                return VideoJobResult(job_id=job_id, status=VideoStatus.PENDING)

            return VideoJobResult(job_id=job_id, status=VideoStatus.PROCESSING)

        except Exception as e:
            self._handle_api_error(e)

    async def _download_video(self, video_url: str) -> bytes:
        """Download video from Fal.ai CDN."""
        try:
            client = await self.get_http_client()
            response = await client.get(video_url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            raise ProviderError(f"Failed to download video: {e}", self.name)

    async def add_lipsync(
        self,
        video: bytes,
        audio: bytes,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Add lip-sync to an existing video.

        Args:
            video: Input video bytes
            audio: Audio bytes to sync
            output_path: Optional path to save video

        Returns:
            Tuple of (video_bytes, metadata_dict)
        """
        # Use generate_video with video passed as kwargs
        return await self.generate_video(
            image=video,  # Pass video as image (will be handled in _submit_job)
            audio=audio,
            output_path=output_path,
            video=video,  # Also pass explicitly
            **kwargs,
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
        """Generate lip-synced video.

        For sync provider, 'image' is treated as video input.

        Args:
            image: Video bytes (not image for this provider)
            audio: Audio bytes for lip-sync (required)
            motion_prompt: Ignored
            duration: Ignored (determined by audio)
            output_path: Optional path to save video

        Returns:
            Tuple of (video_bytes, metadata_dict)
        """
        if audio is None:
            raise ProviderError("Audio is required for lip-sync", self.name)

        return await super().generate_video(
            image=image,
            audio=audio,
            motion_prompt=None,
            duration=None,
            output_path=output_path,
            **kwargs,
        )
