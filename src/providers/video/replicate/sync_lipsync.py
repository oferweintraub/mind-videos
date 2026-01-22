"""Sync lipsync-2-pro provider using Replicate (fallback)."""

import base64
import logging
from pathlib import Path
from typing import Optional

import replicate

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


class SyncLipsyncReplicateProvider(ExtendedVideoProvider):
    """Sync lipsync-2-pro via Replicate.

    Fallback provider when Fal.ai is unavailable.
    """

    DEFAULT_MODEL = "sync/lipsync-2-pro"

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
            name="replicate_sync_lipsync",
            api_key=api_key,
            model_id=model_id or self.DEFAULT_MODEL,
            resolution=resolution,
            poll_interval=poll_interval,
            max_poll_time=max_poll_time,
            retry_config=retry_config,
            timeout=timeout,
        )
        self._client = replicate.Client(api_token=api_key)

    def _encode_media(self, data: bytes, media_type: str) -> str:
        """Encode bytes as data URI."""
        b64_data = base64.b64encode(data).decode("utf-8")
        return f"data:{media_type};base64,{b64_data}"

    def _handle_api_error(self, error: Exception) -> None:
        """Convert Replicate errors to provider errors."""
        error_str = str(error).lower()

        if "401" in error_str or "unauthorized" in error_str:
            raise AuthenticationError("Invalid Replicate API token", self.name)

        if "429" in error_str or "rate limit" in error_str:
            raise RateLimitError("Replicate rate limit exceeded", self.name, retry_after=60.0)

        raise ProviderError(str(error), self.name)

    async def health_check(self) -> bool:
        """Check if Replicate sync is accessible."""
        try:
            self._client.models.get(self.model_id.split(":")[0])
            return True
        except Exception as e:
            logger.error(f"Sync Replicate health check failed: {e}")
            return False

    async def _submit_job(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs,
    ) -> str:
        """Submit a lip-sync job to Replicate."""
        try:
            video_bytes = kwargs.get("video", image)
            video_uri = self._encode_media(video_bytes, "video/mp4")

            if audio is None:
                raise ProviderError("Audio is required for lip-sync", self.name)

            audio_uri = self._encode_media(audio, "audio/mpeg")

            input_data = {
                "video": video_uri,
                "audio": audio_uri,
            }

            prediction = self._client.predictions.create(
                model=self.model_id,
                input=input_data,
            )

            return prediction.id

        except ProviderError:
            raise
        except Exception as e:
            self._handle_api_error(e)

    async def _check_job_status(self, job_id: str) -> VideoJobResult:
        """Check status of a Replicate sync prediction."""
        try:
            prediction = self._client.predictions.get(job_id)

            status_map = {
                "starting": VideoStatus.PENDING,
                "processing": VideoStatus.PROCESSING,
                "succeeded": VideoStatus.COMPLETED,
                "failed": VideoStatus.FAILED,
                "canceled": VideoStatus.FAILED,
            }

            status = status_map.get(prediction.status, VideoStatus.PROCESSING)

            if status == VideoStatus.COMPLETED:
                output = prediction.output
                video_url = None

                if isinstance(output, str):
                    video_url = output
                elif isinstance(output, list) and output:
                    video_url = output[0]
                elif isinstance(output, dict):
                    video_url = output.get("video") or output.get("output")

                return VideoJobResult(
                    job_id=job_id,
                    status=VideoStatus.COMPLETED,
                    video_url=video_url,
                    metadata={"model": prediction.model, "metrics": prediction.metrics},
                )

            elif status == VideoStatus.FAILED:
                return VideoJobResult(
                    job_id=job_id,
                    status=VideoStatus.FAILED,
                    error_message=prediction.error,
                )

            return VideoJobResult(job_id=job_id, status=status)

        except Exception as e:
            self._handle_api_error(e)

    async def _download_video(self, video_url: str) -> bytes:
        """Download video from Replicate CDN."""
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
        return await self.generate_video(
            image=video,
            audio=audio,
            output_path=output_path,
            video=video,
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
            duration: Ignored
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
