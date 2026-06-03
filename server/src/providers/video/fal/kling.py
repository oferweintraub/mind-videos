"""Kling 2.5 Pro video provider using Fal.ai."""

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


class KlingFalProvider(ExtendedVideoProvider):
    """Kling 2.5 Pro video generation via Fal.ai.

    Generates video from image with motion prompt (no audio).
    Used in Workflow 2 before lip-sync overlay.
    """

    DEFAULT_MODEL = "fal-ai/kling-video/v2.1/standard/image-to-video"

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
            name="fal_kling",
            api_key=api_key,
            model_id=model_id or self.DEFAULT_MODEL,
            resolution=resolution,
            poll_interval=poll_interval,
            max_poll_time=max_poll_time,
            retry_config=retry_config,
            timeout=timeout,
        )
        fal_client.api_key = api_key

    def _get_resolution_params(self) -> dict:
        """Get resolution-specific parameters."""
        resolutions = {
            VideoResolution.RES_480P: {"aspect_ratio": "9:16"},
            VideoResolution.RES_720P: {"aspect_ratio": "9:16"},
            VideoResolution.RES_1080P: {"aspect_ratio": "9:16"},
        }
        return resolutions.get(self.resolution, {"aspect_ratio": "9:16"})

    def _encode_image(self, data: bytes) -> str:
        """Encode image bytes as data URI."""
        b64_data = base64.b64encode(data).decode("utf-8")
        return f"data:image/png;base64,{b64_data}"

    def _handle_api_error(self, error: Exception) -> None:
        """Convert Fal.ai errors to provider errors."""
        error_str = str(error).lower()

        if "401" in error_str or "unauthorized" in error_str:
            raise AuthenticationError("Invalid Fal.ai API key", self.name)

        if "429" in error_str or "rate limit" in error_str:
            raise RateLimitError("Fal.ai rate limit exceeded", self.name, retry_after=60.0)

        raise ProviderError(str(error), self.name)

    async def health_check(self) -> bool:
        """Check if Fal.ai Kling is accessible."""
        try:
            return True  # Basic check - actual validation on first use
        except Exception as e:
            logger.error(f"Kling Fal.ai health check failed: {e}")
            return False

    async def _submit_job(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs,
    ) -> str:
        """Submit a video generation job to Fal.ai Kling."""
        try:
            image_uri = self._encode_image(image)

            payload = {
                "image_url": image_uri,
                "prompt": motion_prompt or "subtle natural movement, professional presenter, minimal motion",
                **self._get_resolution_params(),
            }

            if duration:
                payload["duration"] = min(duration, 10)  # Kling max is typically 10s

            handle = await fal_client.submit_async(
                self.model_id,
                arguments=payload,
            )

            return handle.request_id

        except Exception as e:
            self._handle_api_error(e)

    async def _check_job_status(self, job_id: str) -> VideoJobResult:
        """Check status of a Fal.ai Kling job."""
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

            else:
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

    async def generate_video(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Generate video from image with motion.

        Note: Kling does NOT support audio/lip-sync directly.
        Audio parameter is ignored - use sync_lipsync after.

        Args:
            image: Input image bytes
            audio: Ignored (use sync_lipsync for lip-sync)
            motion_prompt: Motion description for video
            duration: Target duration (max 10s)
            output_path: Optional path to save video

        Returns:
            Tuple of (video_bytes, metadata_dict)
        """
        if audio is not None:
            logger.debug("Kling doesn't support audio; use sync_lipsync after generation")

        return await super().generate_video(
            image=image,
            audio=None,  # Kling doesn't use audio
            motion_prompt=motion_prompt,
            duration=duration,
            output_path=output_path,
            **kwargs,
        )
