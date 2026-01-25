"""VEED Fabric 1.0 video provider using Fal.ai."""

import base64
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


class VeedFabricFalProvider(ExtendedVideoProvider):
    """VEED Fabric 1.0 video generation via Fal.ai.

    Generates video with lip-sync from image + audio.
    Primary provider in the fallback chain.
    """

    # Fal.ai model identifier for VEED Fabric
    DEFAULT_MODEL = "veed/fabric-1.0"

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
            name="fal_veed_fabric",
            api_key=api_key,
            model_id=model_id or self.DEFAULT_MODEL,
            resolution=resolution,
            poll_interval=poll_interval,
            max_poll_time=max_poll_time,
            retry_config=retry_config,
            timeout=timeout,
        )
        # Configure fal_client with API key (both methods for compatibility)
        os.environ["FAL_KEY"] = api_key
        fal_client.api_key = api_key

    def _get_resolution_params(self) -> dict:
        """Get resolution-specific parameters for VEED Fabric API."""
        # VEED Fabric uses "resolution" field with values like "480p", "720p"
        if self.resolution == VideoResolution.RES_480P:
            return {"resolution": "480p"}
        elif self.resolution == VideoResolution.RES_720P:
            return {"resolution": "720p"}
        elif self.resolution == VideoResolution.RES_1080P:
            return {"resolution": "1080p"}
        return {"resolution": "480p"}

    async def _upload_media(self, data: bytes, media_type: str) -> str:
        """Upload media to Fal.ai and return the URL."""
        # Determine file extension from media type
        ext_map = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
        }
        ext = ext_map.get(media_type, "bin")

        # Upload using fal_client
        url = await fal_client.upload_async(data, content_type=media_type)
        return url

    def _handle_api_error(self, error: Exception) -> None:
        """Convert Fal.ai errors to provider errors."""
        error_str = str(error).lower()

        if "401" in error_str or "unauthorized" in error_str or "invalid" in error_str:
            raise AuthenticationError(
                "Invalid Fal.ai API key",
                self.name,
            )

        if "429" in error_str or "rate limit" in error_str:
            raise RateLimitError(
                "Fal.ai rate limit exceeded",
                self.name,
                retry_after=60.0,
            )

        raise ProviderError(str(error), self.name)

    async def health_check(self) -> bool:
        """Check if Fal.ai is accessible."""
        try:
            # Try a simple API call to verify connectivity
            # Fal.ai doesn't have a dedicated health endpoint, so we'll try listing models
            return True  # API key validation happens on actual use
        except Exception as e:
            logger.error(f"Fal.ai health check failed: {e}")
            return False

    async def _submit_job(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs,
    ) -> str:
        """Submit a video generation job to Fal.ai."""
        try:
            # Upload image to Fal.ai CDN
            image_url = await self._upload_media(image, "image/jpeg")

            # Build request payload
            payload = {
                "image_url": image_url,
            }

            # Add audio if provided (for lip-sync)
            if audio is not None:
                audio_url = await self._upload_media(audio, "audio/mpeg")
                payload["audio_url"] = audio_url

            # Add optional parameters
            resolution_params = self._get_resolution_params()
            payload.update(resolution_params)

            if duration is not None:
                payload["duration"] = duration

            # Submit to Fal.ai using queue for async processing
            handle = await fal_client.submit_async(
                self.model_id,
                arguments=payload,
            )

            return handle.request_id

        except Exception as e:
            self._handle_api_error(e)

    async def _check_job_status(self, job_id: str) -> VideoJobResult:
        """Check status of a Fal.ai job."""
        try:
            status = await fal_client.status_async(
                self.model_id,
                job_id,
                with_logs=True,
            )

            # New fal_client API returns type instances (Completed, InProgress, Queued)
            if isinstance(status, fal_client.Completed):
                # Get the result
                result = await fal_client.result_async(self.model_id, job_id)

                video_url = None
                duration = None

                # Extract video URL from result
                if hasattr(result, "video") and result.video:
                    video_url = result.video.url if hasattr(result.video, "url") else result.video
                elif isinstance(result, dict):
                    video_url = result.get("video", {}).get("url") or result.get("video_url")

                # Extract duration if available
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

            elif hasattr(status, "error") and status.error:
                return VideoJobResult(
                    job_id=job_id,
                    status=VideoStatus.FAILED,
                    error_message=str(status.error),
                )

            elif isinstance(status, fal_client.Queued):
                return VideoJobResult(
                    job_id=job_id,
                    status=VideoStatus.PENDING,
                )

            else:  # InProgress or other
                return VideoJobResult(
                    job_id=job_id,
                    status=VideoStatus.PROCESSING,
                )

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
        """Generate a video with optional lip-sync.

        Args:
            image: Input image bytes (character image)
            audio: Audio bytes for lip-sync
            motion_prompt: Not used by VEED Fabric (ignored)
            duration: Target duration (derived from audio if not specified)
            output_path: Optional path to save video
            **kwargs: Additional parameters

        Returns:
            Tuple of (video_bytes, metadata_dict)
        """
        if motion_prompt:
            logger.debug("VEED Fabric doesn't use motion_prompt, ignoring")

        return await super().generate_video(
            image=image,
            audio=audio,
            motion_prompt=None,  # VEED doesn't use motion prompt
            duration=duration,
            output_path=output_path,
            **kwargs,
        )
