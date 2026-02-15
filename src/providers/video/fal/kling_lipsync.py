"""Kling Avatar v2 video provider using Fal.ai.

Generates talking-head video from image + audio in a single step.
"""

import logging
import os
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


class KlingAvatarFalProvider(ExtendedVideoProvider):
    """Kling Avatar v2 via Fal.ai.

    Single-step image+audio → talking-head video.
    Uses fal-ai/kling-video/ai-avatar/v2/standard.
    """

    DEFAULT_MODEL = "fal-ai/kling-video/ai-avatar/v2/standard"

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
            name="fal_kling_avatar",
            api_key=api_key,
            model_id=model_id or self.DEFAULT_MODEL,
            resolution=resolution,
            poll_interval=poll_interval,
            max_poll_time=max_poll_time,
            retry_config=retry_config,
            timeout=timeout,
        )
        os.environ["FAL_KEY"] = api_key
        fal_client.api_key = api_key

    def _handle_api_error(self, error: Exception) -> None:
        error_str = str(error).lower()
        if "401" in error_str or "unauthorized" in error_str:
            raise AuthenticationError("Invalid Fal.ai API key", self.name)
        if "429" in error_str or "rate limit" in error_str:
            raise RateLimitError("Fal.ai rate limit exceeded", self.name, retry_after=60.0)
        raise ProviderError(str(error), self.name)

    async def health_check(self) -> bool:
        try:
            return True
        except Exception as e:
            logger.error(f"Kling Avatar health check failed: {e}")
            return False

    async def _submit_job(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs,
    ) -> str:
        """Submit avatar generation: image + audio → talking-head video."""
        try:
            if audio is None:
                raise ProviderError("Audio is required for Kling Avatar", self.name)

            image_url = await fal_client.upload_async(image, content_type="image/png")
            audio_url = await fal_client.upload_async(audio, content_type="audio/mpeg")

            payload = {
                "image_url": image_url,
                "audio_url": audio_url,
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
        try:
            status = await fal_client.status_async(
                self.model_id,
                job_id,
                with_logs=True,
            )

            if isinstance(status, fal_client.Completed):
                result = await fal_client.result_async(self.model_id, job_id)

                video_url = None
                duration = None

                if isinstance(result, dict):
                    video_url = result.get("video", {}).get("url") or result.get("video_url")
                    duration = result.get("duration")
                elif hasattr(result, "video") and result.video:
                    video_url = result.video.url if hasattr(result.video, "url") else result.video
                    duration = getattr(result, "duration", None)

                return VideoJobResult(
                    job_id=job_id,
                    status=VideoStatus.COMPLETED,
                    video_url=video_url,
                    duration=duration,
                    metadata={"raw_result": result if isinstance(result, dict) else {}},
                )

            elif hasattr(status, "error") and status.error:
                return VideoJobResult(
                    job_id=job_id,
                    status=VideoStatus.FAILED,
                    error_message=str(status.error),
                )

            elif isinstance(status, fal_client.Queued):
                return VideoJobResult(job_id=job_id, status=VideoStatus.PENDING)

            else:
                return VideoJobResult(job_id=job_id, status=VideoStatus.PROCESSING)

        except Exception as e:
            self._handle_api_error(e)

    async def _download_video(self, video_url: str) -> bytes:
        try:
            client = await self.get_http_client()
            response = await client.get(video_url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            raise ProviderError(f"Failed to download video: {e}", self.name)

    async def generate_video(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Generate talking-head video from image + audio.

        Args:
            image: Input face image bytes
            audio: Audio bytes (required)
            motion_prompt: Ignored
            duration: Ignored (determined by audio)
            output_path: Optional path to save video

        Returns:
            Tuple of (video_bytes, metadata_dict)
        """
        if audio is None:
            raise ProviderError("Audio is required for Kling Avatar", self.name)

        return await super().generate_video(
            image=image,
            audio=audio,
            motion_prompt=None,
            duration=None,
            output_path=output_path,
            **kwargs,
        )
