"""Nano Banana Pro image provider using Google AI (Imagen 3)."""

import base64
import logging
from pathlib import Path
from typing import Optional

import google.generativeai as genai

from ..base import (
    AuthenticationError,
    BaseImageProvider,
    ContentError,
    ProviderError,
    RateLimitError,
    RetryConfig,
)

logger = logging.getLogger(__name__)


class NanoBananaProvider(BaseImageProvider):
    """Nano Banana Pro image generation via Google AI.

    Uses Imagen 3 for high-quality character image generation
    with consistency features for reference images.
    """

    DEFAULT_MODEL = "imagen-3.0-generate-002"

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

        # Configure Google AI
        genai.configure(api_key=api_key)

    async def health_check(self) -> bool:
        """Check if Google AI is accessible."""
        try:
            # List available models to verify connectivity
            models = list(genai.list_models())
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
                # Get the Imagen model
                imagen = genai.ImageGenerationModel(self.model)

                # Build generation config
                config = {
                    "number_of_images": 1,
                    "aspect_ratio": aspect,
                    "safety_filter_level": "block_only_high",
                    "person_generation": "allow_adult",
                }

                # Add negative prompt if provided
                if negative_prompt:
                    config["negative_prompt"] = negative_prompt

                # Generate image
                response = imagen.generate_images(
                    prompt=prompt,
                    **config,
                )

                # Get the first image
                if not response.images:
                    raise ProviderError("No images generated", self.name)

                image = response.images[0]

                # Get image bytes
                image_bytes = image._pil_image.tobytes() if hasattr(image, '_pil_image') else None

                if image_bytes is None:
                    # Try to get from base64 if available
                    if hasattr(image, 'data'):
                        image_bytes = base64.b64decode(image.data)
                    elif hasattr(image, '_image_bytes'):
                        image_bytes = image._image_bytes
                    else:
                        # Save to temp file and read back
                        import io
                        buffer = io.BytesIO()
                        image._pil_image.save(buffer, format='PNG')
                        image_bytes = buffer.getvalue()

                return image_bytes

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
        **kwargs,
    ) -> list[tuple[bytes, dict]]:
        """Generate multiple images from a list of prompts.

        Args:
            prompts: List of image prompts
            output_dir: Directory to save images
            **kwargs: Additional parameters for each generation

        Returns:
            List of (image_bytes, metadata) tuples
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        results = []

        for i, prompt in enumerate(prompts):
            output_path = output_dir / f"image_{i:02d}.png"

            try:
                image_bytes, metadata = await self.generate_image(
                    prompt=prompt,
                    output_path=output_path,
                    **kwargs,
                )
                metadata["index"] = i
                results.append((image_bytes, metadata))
                logger.info(f"Generated image {i+1}/{len(prompts)}")

            except Exception as e:
                logger.error(f"Failed to generate image {i+1}: {e}")
                results.append((None, {"error": str(e), "index": i}))

        return results
