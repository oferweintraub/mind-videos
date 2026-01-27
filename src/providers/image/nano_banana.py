"""Nano Banana Pro image provider using Google AI."""

import logging
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from ..base import (
    AuthenticationError,
    BaseImageProvider,
    BatchItemResult,
    BatchResult,
    ContentError,
    ProviderError,
    RateLimitError,
    RetryConfig,
)

logger = logging.getLogger(__name__)


class NanoBananaProvider(BaseImageProvider):
    """Nano Banana Pro image generation via Google AI.

    Primary method: generate_with_reference() for character consistency.
    """

    NANO_BANANA_MODEL = "nano-banana-pro-preview"

    def __init__(
        self,
        api_key: str,
        aspect_ratio: str = "9:16",
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 60.0,
    ):
        super().__init__(
            name="nano_banana",
            api_key=api_key,
            retry_config=retry_config,
            timeout=timeout,
        )
        self.aspect_ratio = aspect_ratio
        self._client = genai.Client(api_key=api_key)

    async def health_check(self) -> bool:
        """Check if Google AI is accessible."""
        try:
            models = list(self._client.models.list())
            return len(models) > 0
        except Exception as e:
            logger.error(f"Nano Banana health check failed: {e}")
            return False

    def _handle_api_error(self, error: Exception) -> None:
        """Convert Google AI errors to provider errors."""
        error_str = str(error).lower()

        if "api key" in error_str or "invalid" in error_str or "401" in error_str:
            raise AuthenticationError("Invalid Google API key", self.name)

        if "429" in error_str or "rate" in error_str or "quota" in error_str:
            raise RateLimitError("Google AI rate limit exceeded", self.name, retry_after=60.0)

        if "safety" in error_str or "blocked" in error_str:
            raise ContentError(f"Image generation blocked by safety filters: {error}", self.name)

        raise ProviderError(str(error), self.name)

    async def generate_image(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Generate an image, optionally using a reference image for consistency.

        Args:
            prompt: Image generation prompt
            reference_image: Optional reference image bytes for character consistency
            output_path: Optional path to save image

        Returns:
            Tuple of (image_bytes, metadata_dict)
        """
        async def _generate():
            try:
                if reference_image:
                    # Use Nano Banana Pro with reference
                    response = self._client.models.generate_content(
                        model=self.NANO_BANANA_MODEL,
                        contents=[
                            types.Part.from_bytes(data=reference_image, mime_type='image/png'),
                            prompt,
                        ],
                        config=types.GenerateContentConfig(response_modalities=['image', 'text'])
                    )
                else:
                    # Generate without reference
                    response = self._client.models.generate_content(
                        model=self.NANO_BANANA_MODEL,
                        contents=[prompt],
                        config=types.GenerateContentConfig(response_modalities=['image', 'text'])
                    )

                # Extract image from response
                if response.candidates:
                    for candidate in response.candidates:
                        if candidate.content and candidate.content.parts:
                            for part in candidate.content.parts:
                                if hasattr(part, 'inline_data') and part.inline_data:
                                    return part.inline_data.data

                raise ProviderError("No image generated in response", self.name)

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
            "model": self.NANO_BANANA_MODEL,
            "has_reference": reference_image is not None,
            "provider": self.name,
        }

        return image_bytes, metadata

    async def generate_batch(
        self,
        prompts: list[str],
        output_dir: Path,
        reference_image: Optional[bytes] = None,
        fail_fast: bool = False,
        **kwargs,
    ) -> BatchResult[tuple[bytes, dict]]:
        """Generate multiple images from prompts.

        Args:
            prompts: List of image prompts
            output_dir: Directory to save images
            reference_image: Optional reference for all images
            fail_fast: Stop on first failure

        Returns:
            BatchResult with success/failure tracking
        """
        import time

        start_time = time.time()
        output_dir.mkdir(parents=True, exist_ok=True)
        batch_result = BatchResult[tuple[bytes, dict]]()

        for i, prompt in enumerate(prompts):
            output_path = output_dir / f"image_{i:02d}.png"

            try:
                image_bytes, metadata = await self.generate_image(
                    prompt=prompt,
                    reference_image=reference_image,
                    output_path=output_path,
                    **kwargs,
                )
                metadata["index"] = i

                batch_result.items.append(
                    BatchItemResult(index=i, success=True, data=(image_bytes, metadata))
                )
                logger.info(f"Generated image {i+1}/{len(prompts)}")

            except ProviderError as e:
                logger.error(f"Failed to generate image {i+1}: {e}")
                batch_result.items.append(
                    BatchItemResult(index=i, success=False, error=e)
                )
                if fail_fast:
                    break

            except Exception as e:
                logger.error(f"Unexpected error generating image {i+1}: {e}")
                batch_result.items.append(
                    BatchItemResult(index=i, success=False, error=ProviderError(str(e), self.name))
                )
                if fail_fast:
                    break

        batch_result.total_duration = time.time() - start_time
        logger.info(
            f"Batch complete: {batch_result.success_count}/{len(prompts)} succeeded "
            f"in {batch_result.total_duration:.2f}s"
        )

        return batch_result
