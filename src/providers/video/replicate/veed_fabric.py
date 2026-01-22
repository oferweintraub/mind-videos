"""VEED Fabric 1.0 video provider using Replicate (fallback)."""

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


class VeedFabricReplicateProvider(ExtendedVideoProvider):
    """VEED Fabric 1.0 video generation via Replicate.

    Fallback provider when Fal.ai is unavailable.
    """

    # Replicate model identifier for VEED Fabric
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
            name="replicate_veed_fabric",
            api_key=api_key,
            model_id=model_id or self.DEFAULT_MODEL,
            resolution=resolution,
            poll_interval=poll_interval,
            max_poll_time=max_poll_time,
            retry_config=retry_config,
            timeout=timeout,
        )
        # Configure replicate client
        self._client = replicate.Client(api_token=api_key)

    def _get_resolution_params(self) -> dict:
        """Get resolution-specific parameters for Replicate."""
        if self.resolution == VideoResolution.RES_480P:
            return {"width": 854, "height": 480}
        elif self.resolution == VideoResolution.RES_720P:
            return {"width": 1280, "height": 720}
        elif self.resolution == VideoResolution.RES_1080P:
            return {"width": 1920, "height": 1080}
        return {"width": 854, "height": 480}

    def _encode_media(self, data: bytes, media_type: str) -> str:
        """Encode bytes as data URI for Replicate."""
        b64_data = base64.b64encode(data).decode("utf-8")
        return f"data:{media_type};base64,{b64_data}"

    def _handle_api_error(self, error: Exception) -> None:
        """Convert Replicate errors to provider errors."""
        error_str = str(error).lower()

        if "401" in error_str or "unauthorized" in error_str or "invalid token" in error_str:
            raise AuthenticationError(
                "Invalid Replicate API token",
                self.name,
            )

        if "429" in error_str or "rate limit" in error_str:
            raise RateLimitError(
                "Replicate rate limit exceeded",
                self.name,
                retry_after=60.0,
            )

        raise ProviderError(str(error), self.name)

    async def health_check(self) -> bool:
        """Check if Replicate is accessible."""
        try:
            # Try to get model info
            self._client.models.get(self.model_id.split(":")[0])
            return True
        except Exception as e:
            logger.error(f"Replicate health check failed: {e}")
            return False

    async def _submit_job(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs,
    ) -> str:
        """Submit a video generation job to Replicate."""
        try:
            # Encode image as data URI
            image_uri = self._encode_media(image, "image/png")

            # Build input payload
            input_data = {
                "image": image_uri,
            }

            # Add audio if provided (for lip-sync)
            if audio is not None:
                audio_uri = self._encode_media(audio, "audio/mpeg")
                input_data["audio"] = audio_uri

            # Add resolution parameters
            resolution_params = self._get_resolution_params()
            input_data.update(resolution_params)

            if duration is not None:
                input_data["duration"] = duration

            # Create prediction (async)
            prediction = self._client.predictions.create(
                model=self.model_id,
                input=input_data,
            )

            return prediction.id

        except Exception as e:
            self._handle_api_error(e)

    async def _check_job_status(self, job_id: str) -> VideoJobResult:
        """Check status of a Replicate prediction."""
        try:
            prediction = self._client.predictions.get(job_id)

            # Map Replicate status to our status enum
            status_map = {
                "starting": VideoStatus.PENDING,
                "processing": VideoStatus.PROCESSING,
                "succeeded": VideoStatus.COMPLETED,
                "failed": VideoStatus.FAILED,
                "canceled": VideoStatus.FAILED,
            }

            status = status_map.get(prediction.status, VideoStatus.PROCESSING)

            if status == VideoStatus.COMPLETED:
                # Get output URL
                output = prediction.output
                video_url = None

                if isinstance(output, str):
                    video_url = output
                elif isinstance(output, list) and len(output) > 0:
                    video_url = output[0]
                elif isinstance(output, dict):
                    video_url = output.get("video") or output.get("output")

                return VideoJobResult(
                    job_id=job_id,
                    status=VideoStatus.COMPLETED,
                    video_url=video_url,
                    metadata={
                        "model": prediction.model,
                        "version": prediction.version,
                        "metrics": prediction.metrics,
                    },
                )

            elif status == VideoStatus.FAILED:
                return VideoJobResult(
                    job_id=job_id,
                    status=VideoStatus.FAILED,
                    error_message=prediction.error,
                )

            else:
                return VideoJobResult(
                    job_id=job_id,
                    status=status,
                )

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
            motion_prompt=None,
            duration=duration,
            output_path=output_path,
            **kwargs,
        )
