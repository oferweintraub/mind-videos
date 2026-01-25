"""Nano Banana Pro image provider using Google AI (Imagen 3)."""

import base64
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

    Uses Nano Banana Pro (Gemini 3 Pro Image) for high-quality character
    image generation with reference image support for consistency.

    Supports two modes:
    - generate_image: Basic text-to-image using Imagen 4.0
    - generate_mosaic: Reference-based mosaic using Nano Banana Pro
    """

    DEFAULT_MODEL = "imagen-4.0-generate-001"
    NANO_BANANA_MODEL = "nano-banana-pro-preview"

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
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
        self.model = model or self.DEFAULT_MODEL
        self.aspect_ratio = aspect_ratio

        # Create Google AI client
        self._client = genai.Client(api_key=api_key)

    async def health_check(self) -> bool:
        """Check if Google AI is accessible."""
        try:
            # List available models to verify connectivity
            models = list(self._client.models.list())
            return len(models) > 0
        except Exception as e:
            logger.error(f"Nano Banana health check failed: {e}")
            return False

    def _handle_api_error(self, error: Exception) -> None:
        """Convert Google AI errors to provider errors."""
        error_str = str(error).lower()

        if "api key" in error_str or "invalid" in error_str or "401" in error_str:
            raise AuthenticationError(
                "Invalid Google API key",
                self.name,
            )

        if "429" in error_str or "rate" in error_str or "quota" in error_str:
            raise RateLimitError(
                "Google AI rate limit exceeded",
                self.name,
                retry_after=60.0,
            )

        if "safety" in error_str or "blocked" in error_str:
            raise ContentError(
                f"Image generation blocked by safety filters: {error}",
                self.name,
            )

        raise ProviderError(str(error), self.name)

    def _parse_aspect_ratio(self, aspect_ratio: str) -> tuple[int, int]:
        """Parse aspect ratio string to width/height."""
        ratios = {
            "1:1": (1024, 1024),
            "16:9": (1792, 1024),
            "9:16": (1024, 1792),
            "4:3": (1365, 1024),
            "3:4": (1024, 1365),
        }
        return ratios.get(aspect_ratio, (1024, 1792))

    async def generate_image(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        aspect_ratio: Optional[str] = None,
        output_path: Optional[Path] = None,
        negative_prompt: Optional[str] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Generate an image from a prompt.

        Args:
            prompt: Image generation prompt
            reference_image: Optional reference image for style/character consistency
            aspect_ratio: Desired aspect ratio (e.g., "9:16")
            output_path: Optional path to save image
            negative_prompt: What to avoid in the image
            **kwargs: Additional parameters

        Returns:
            Tuple of (image_bytes, metadata_dict)
        """
        aspect = aspect_ratio or self.aspect_ratio

        async def _generate():
            try:
                # Build generation config using new SDK types
                # Note: negative_prompt is not supported in the current Gemini API
                # Imagen 4.0 only supports "block_low_and_above" for safety filter
                config = types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect,
                    safety_filter_level="block_low_and_above",
                    person_generation="allow_adult",
                )

                # Generate image using new client API
                response = self._client.models.generate_images(
                    model=self.model,
                    prompt=prompt,
                    config=config,
                )

                # Get the first image
                if not response.generated_images:
                    raise ProviderError("No images generated", self.name)

                image = response.generated_images[0]

                # Get image bytes from the new SDK format
                if hasattr(image, 'image') and hasattr(image.image, 'image_bytes'):
                    image_bytes = image.image.image_bytes
                elif hasattr(image, 'image_bytes'):
                    image_bytes = image.image_bytes
                else:
                    raise ProviderError("Could not extract image bytes from response", self.name)

                return image_bytes

            except ProviderError:
                raise
            except Exception as e:
                self._handle_api_error(e)

        result = await self._retry_operation(_generate, "generate_image")

        if not result.success:
            raise result.error or ProviderError("Image generation failed", self.name)

        image_bytes = result.data

        # Save to file if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            logger.info(f"Image saved to {output_path}")

        metadata = {
            "model": self.model,
            "aspect_ratio": aspect,
            "prompt_length": len(prompt),
            "provider": self.name,
        }

        return image_bytes, metadata

    async def generate_character_image(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        expression: str = "neutral",
        camera_angle: str = "medium",
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Generate a character image with specific expression and angle.

        Args:
            prompt: Character description prompt
            reference_image: Optional reference for consistency
            expression: Desired expression (neutral, happy, serious, etc.)
            camera_angle: Camera angle (close_up, medium, wide, etc.)
            output_path: Optional path to save image
            **kwargs: Additional parameters

        Returns:
            Tuple of (image_bytes, metadata_dict)
        """
        # Enhance prompt with expression and angle
        enhanced_prompt = (
            f"{prompt} "
            f"The subject has a {expression} expression. "
            f"{camera_angle.replace('_', ' ')} shot. "
            f"Professional portrait photography, studio lighting, "
            f"sharp focus, high quality, 4K resolution."
        )

        # Standard negative prompt for character images
        negative_prompt = (
            "blurry, low quality, distorted features, deformed, "
            "unprofessional, inappropriate, multiple people, "
            "text, watermark, logo, cartoon, anime, illustration"
        )

        return await self.generate_image(
            prompt=enhanced_prompt,
            reference_image=reference_image,
            output_path=output_path,
            negative_prompt=negative_prompt,
            **kwargs,
        )

    async def generate_batch(
        self,
        prompts: list[str],
        output_dir: Path,
        fail_fast: bool = False,
        **kwargs,
    ) -> BatchResult[tuple[bytes, dict]]:
        """Generate multiple images from a list of prompts.

        Args:
            prompts: List of image prompts
            output_dir: Directory to save images
            fail_fast: If True, stop on first failure
            **kwargs: Additional parameters for each generation

        Returns:
            BatchResult with structured success/failure tracking
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
                    output_path=output_path,
                    **kwargs,
                )
                metadata["index"] = i

                batch_result.items.append(
                    BatchItemResult(
                        index=i,
                        success=True,
                        data=(image_bytes, metadata),
                    )
                )
                logger.info(f"Generated image {i+1}/{len(prompts)}")

            except ProviderError as e:
                logger.error(f"Failed to generate image {i+1}: {e}")
                batch_result.items.append(
                    BatchItemResult(
                        index=i,
                        success=False,
                        error=e,
                    )
                )
                if fail_fast:
                    logger.warning(f"Batch generation stopped at image {i+1} due to fail_fast")
                    break

            except Exception as e:
                logger.error(f"Unexpected error generating image {i+1}: {e}")
                batch_result.items.append(
                    BatchItemResult(
                        index=i,
                        success=False,
                        error=ProviderError(str(e), self.name),
                    )
                )
                if fail_fast:
                    logger.warning(f"Batch generation stopped at image {i+1} due to fail_fast")
                    break

        batch_result.total_duration = time.time() - start_time

        # Log summary
        logger.info(
            f"Batch complete: {batch_result.success_count}/{len(prompts)} succeeded, "
            f"{batch_result.failure_count} failed in {batch_result.total_duration:.2f}s"
        )

        return batch_result

    async def generate_batch_legacy(
        self,
        prompts: list[str],
        output_dir: Path,
        **kwargs,
    ) -> list[tuple[bytes, dict]]:
        """Legacy batch generation returning list format for backwards compatibility.

        Args:
            prompts: List of image prompts
            output_dir: Directory to save images
            **kwargs: Additional parameters for each generation

        Returns:
            List of (image_bytes, metadata) tuples - None for failures
        """
        batch_result = await self.generate_batch(prompts, output_dir, **kwargs)

        # Convert to legacy format
        results = []
        for item in batch_result.items:
            if item.success and item.data:
                results.append(item.data)
            else:
                results.append((None, {"error": str(item.error), "index": item.index}))

        return results

    async def generate_mosaic(
        self,
        reference_image: Optional[bytes] = None,
        reference_image_path: Optional[Path] = None,
        character_description: Optional[str] = None,
        settings: Optional[list[str]] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Generate a 2x3 mosaic with 6 character variations using Nano Banana Pro.

        This method uses Nano Banana Pro (Gemini 3 Pro Image) which supports
        reference images for character consistency. It generates a single image
        containing 6 variations of the same character in different settings/poses.

        Args:
            reference_image: Reference image bytes for character consistency
            reference_image_path: Path to reference image (alternative to bytes)
            character_description: Optional text description (used if no reference)
            settings: List of 6 settings/poses for the grid (optional, uses defaults)
            output_path: Optional path to save the mosaic image
            **kwargs: Additional parameters

        Returns:
            Tuple of (mosaic_bytes, metadata_dict)
        """
        # Load reference image if path provided
        if reference_image_path and not reference_image:
            if not reference_image_path.exists():
                raise ProviderError(
                    f"Reference image not found: {reference_image_path}",
                    self.name,
                    recoverable=False,
                )
            reference_image = reference_image_path.read_bytes()

        # Default settings for the 6 grid cells
        default_settings = [
            "sitting on a comfortable sofa in a living room",
            "standing in a modern kitchen",
            "on a sunny balcony with city view",
            "standing confidently with arms crossed",
            "close-up portrait shot",
            "side profile angle",
        ]
        settings = settings or default_settings

        if len(settings) != 6:
            raise ProviderError(
                f"Mosaic requires exactly 6 settings, got {len(settings)}",
                self.name,
                recoverable=False,
            )

        # Build the mosaic prompt
        settings_text = ", ".join([f"({i+1}) {s}" for i, s in enumerate(settings)])

        if reference_image:
            # Use Nano Banana Pro with reference image
            mosaic_prompt = (
                f"Create a 2x3 grid showing this SAME woman in 6 different settings: "
                f"{settings_text}. "
                f"Maintain the exact same face, hair color, and features in all 6 images. "
                f"Professional photography quality, good lighting in each scene."
            )

            async def _generate_with_reference():
                try:
                    response = self._client.models.generate_content(
                        model=self.NANO_BANANA_MODEL,
                        contents=[
                            types.Part.from_bytes(data=reference_image, mime_type='image/png'),
                            mosaic_prompt,
                        ],
                        config=types.GenerateContentConfig(
                            response_modalities=['image', 'text'],
                        )
                    )

                    # Extract generated image from response
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

            result = await self._retry_operation(_generate_with_reference, "generate_mosaic")

            if not result.success:
                raise result.error or ProviderError("Mosaic generation failed", self.name)

            image_bytes = result.data

        else:
            # Fallback to Imagen without reference image
            if not character_description:
                raise ProviderError(
                    "Either reference_image or character_description required",
                    self.name,
                    recoverable=False,
                )

            mosaic_prompt = (
                f"Create a 2x3 grid image showing the SAME person in 6 different scenes. "
                f"The person: {character_description}. "
                f"The 6 scenes arranged in 2 rows of 3: {settings_text}. "
                f"Each cell shows the same person with consistent appearance, face, and features. "
                f"Professional photography quality, good lighting in each scene. "
                f"Clean grid layout with subtle borders between cells."
            )

            image_bytes, _ = await self.generate_image(
                prompt=mosaic_prompt,
                aspect_ratio="3:4",
                output_path=None,  # We'll save below
                **kwargs,
            )

        # Save to file if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            logger.info(f"Mosaic saved to {output_path}")

        metadata = {
            "model": self.NANO_BANANA_MODEL if reference_image else self.model,
            "mosaic": True,
            "grid_size": "2x3",
            "settings": settings,
            "has_reference": reference_image is not None,
            "provider": self.name,
        }

        return image_bytes, metadata
