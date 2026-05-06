"""Qwen-Image-2512 image provider using Fal.ai."""

import logging
import os
from pathlib import Path
from typing import Optional

import fal_client

from ..base import (
    AuthenticationError,
    BaseImageProvider,
    ProviderError,
    RateLimitError,
    RetryConfig,
)

logger = logging.getLogger(__name__)


class QwenImageProvider(BaseImageProvider):
    """Qwen-Image-2512 image generation via Fal.ai.

    Text-to-image model with strong photorealism.
    Does NOT support reference images natively — use prompt-based consistency.
    """

    DEFAULT_MODEL = "fal-ai/qwen-image-2512"

    def __init__(
        self,
        api_key: str,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 60.0,
    ):
        super().__init__(
            name="qwen_image",
            api_key=api_key,
            retry_config=retry_config,
            timeout=timeout,
        )
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
            logger.error(f"Qwen image health check failed: {e}")
            return False

    async def generate_image(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Generate an image from a text prompt.

        Args:
            prompt: Image generation prompt
            reference_image: Not supported by Qwen — ignored with warning
            output_path: Optional path to save image

        Returns:
            Tuple of (image_bytes, metadata_dict)
        """
        if reference_image:
            logger.warning("Qwen-Image does not support reference images; using prompt only")

        async def _generate():
            try:
                payload = {
                    "prompt": prompt,
                    "image_size": {"width": 576, "height": 1024},  # ~9:16
                }

                result = await fal_client.run_async(
                    self.DEFAULT_MODEL,
                    arguments=payload,
                )

                # Extract image URL from result
                image_url = None
                if isinstance(result, dict):
                    images = result.get("images", [])
                    if images:
                        image_url = images[0].get("url") if isinstance(images[0], dict) else images[0]
                    elif result.get("image"):
                        img = result["image"]
                        image_url = img.get("url") if isinstance(img, dict) else img
                elif hasattr(result, "images") and result.images:
                    image_url = result.images[0].url if hasattr(result.images[0], "url") else result.images[0]

                if not image_url:
                    raise ProviderError(f"No image URL in response: {result}", self.name)

                # Download image
                import httpx
                async with httpx.AsyncClient() as http:
                    resp = await http.get(image_url)
                    resp.raise_for_status()
                    return resp.content

            except ProviderError:
                raise
            except Exception as e:
                self._handle_api_error(e)

        result = await self._retry_operation(_generate, "generate_image")
        if not result.success:
            raise result.error or ProviderError("Image generation failed", self.name)

        image_bytes = result.data

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            logger.info(f"Image saved to {output_path}")

        metadata = {
            "model": self.DEFAULT_MODEL,
            "has_reference": False,
            "provider": self.name,
        }

        return image_bytes, metadata
