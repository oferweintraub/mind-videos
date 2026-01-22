"""Base provider interfaces and common utilities."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generic, Optional, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(self, message: str, provider: str, recoverable: bool = True):
        super().__init__(message)
        self.provider = provider
        self.recoverable = recoverable


class RateLimitError(ProviderError):
    """Rate limit exceeded."""

    def __init__(self, message: str, provider: str, retry_after: Optional[float] = None):
        super().__init__(message, provider, recoverable=True)
        self.retry_after = retry_after


class TimeoutError(ProviderError):
    """Operation timed out."""

    pass


class AuthenticationError(ProviderError):
    """Authentication failed."""

    def __init__(self, message: str, provider: str):
        super().__init__(message, provider, recoverable=False)


class ContentError(ProviderError):
    """Content-related error (e.g., inappropriate content)."""

    def __init__(self, message: str, provider: str):
        super().__init__(message, provider, recoverable=False)


class ProviderStatus(str, Enum):
    """Provider operational status."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class ProviderResult(Generic[T]):
    """Result from a provider operation."""

    success: bool
    data: Optional[T] = None
    error: Optional[ProviderError] = None
    attempts: int = 1
    duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """Abstract base class for all providers."""

    def __init__(
        self,
        name: str,
        api_key: str,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 60.0,
    ):
        self.name = name
        self._api_key = api_key
        self.retry_config = retry_config or RetryConfig()
        self.timeout = timeout
        self._status = ProviderStatus.AVAILABLE
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def status(self) -> ProviderStatus:
        """Get provider status."""
        return self._status

    @property
    def is_available(self) -> bool:
        """Check if provider is available."""
        return self._status != ProviderStatus.UNAVAILABLE

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy."""
        pass

    async def _calculate_delay(self, attempt: int, rate_limit_retry: Optional[float] = None) -> float:
        """Calculate delay before retry with exponential backoff."""
        if rate_limit_retry is not None:
            return rate_limit_retry

        delay = min(
            self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt),
            self.retry_config.max_delay,
        )

        if self.retry_config.jitter:
            import random
            delay = delay * (0.5 + random.random())

        return delay

    async def _retry_operation(
        self,
        operation: Callable[[], T],
        operation_name: str = "operation",
    ) -> ProviderResult[T]:
        """Execute operation with retry logic."""
        import time

        start_time = time.time()
        last_error: Optional[ProviderError] = None

        for attempt in range(self.retry_config.max_retries):
            try:
                result = await operation()
                return ProviderResult(
                    success=True,
                    data=result,
                    attempts=attempt + 1,
                    duration=time.time() - start_time,
                )

            except RateLimitError as e:
                last_error = e
                logger.warning(
                    f"{self.name}: Rate limited on {operation_name} "
                    f"(attempt {attempt + 1}/{self.retry_config.max_retries})"
                )
                delay = await self._calculate_delay(attempt, e.retry_after)
                await asyncio.sleep(delay)

            except ProviderError as e:
                last_error = e
                if not e.recoverable:
                    logger.error(f"{self.name}: Non-recoverable error in {operation_name}: {e}")
                    break

                logger.warning(
                    f"{self.name}: Error in {operation_name} "
                    f"(attempt {attempt + 1}/{self.retry_config.max_retries}): {e}"
                )
                delay = await self._calculate_delay(attempt)
                await asyncio.sleep(delay)

            except Exception as e:
                last_error = ProviderError(str(e), self.name)
                logger.warning(
                    f"{self.name}: Unexpected error in {operation_name} "
                    f"(attempt {attempt + 1}/{self.retry_config.max_retries}): {e}"
                )
                delay = await self._calculate_delay(attempt)
                await asyncio.sleep(delay)

        return ProviderResult(
            success=False,
            error=last_error,
            attempts=self.retry_config.max_retries,
            duration=time.time() - start_time,
        )


class BaseLLMProvider(BaseProvider):
    """Base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_model: Optional[type] = None,
        **kwargs,
    ) -> Any:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            response_model: Optional Pydantic model for structured output (via Instructor)
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text or structured response if response_model is provided
        """
        pass


class BaseAudioProvider(BaseProvider):
    """Base class for audio providers."""

    @abstractmethod
    async def generate_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, float]:
        """Generate speech from text.

        Args:
            text: Text to convert to speech
            voice_id: Voice identifier
            output_path: Optional path to save audio
            **kwargs: Additional provider-specific parameters

        Returns:
            Tuple of (audio_bytes, duration_seconds)
        """
        pass


class BaseImageProvider(BaseProvider):
    """Base class for image providers."""

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        aspect_ratio: str = "9:16",
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Generate an image from a prompt.

        Args:
            prompt: Image generation prompt
            reference_image: Optional reference image for consistency
            aspect_ratio: Desired aspect ratio
            output_path: Optional path to save image
            **kwargs: Additional provider-specific parameters

        Returns:
            Tuple of (image_bytes, metadata_dict)
        """
        pass


class BaseVideoProvider(BaseProvider):
    """Base class for video providers."""

    @abstractmethod
    async def generate_video(
        self,
        image: bytes,
        audio: Optional[bytes] = None,
        motion_prompt: Optional[str] = None,
        duration: Optional[float] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """Generate a video from an image.

        Args:
            image: Input image bytes
            audio: Optional audio for lip-sync
            motion_prompt: Optional motion description
            duration: Target duration in seconds
            output_path: Optional path to save video
            **kwargs: Additional provider-specific parameters

        Returns:
            Tuple of (video_bytes, metadata_dict)
        """
        pass

    @abstractmethod
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
            **kwargs: Additional provider-specific parameters

        Returns:
            Tuple of (video_bytes, metadata_dict)
        """
        pass


class FallbackProvider(Generic[T]):
    """Wrapper that handles fallback between primary and secondary providers."""

    def __init__(
        self,
        primary: T,
        fallback: T,
        fallback_on_errors: tuple[type, ...] = (ProviderError,),
    ):
        self.primary = primary
        self.fallback = fallback
        self.fallback_on_errors = fallback_on_errors
        self._using_fallback = False

    @property
    def active_provider(self) -> T:
        """Get the currently active provider."""
        return self.fallback if self._using_fallback else self.primary

    @property
    def is_using_fallback(self) -> bool:
        """Check if currently using fallback provider."""
        return self._using_fallback

    async def execute(
        self,
        method_name: str,
        *args,
        **kwargs,
    ) -> ProviderResult:
        """Execute a method on primary, falling back if needed.

        Args:
            method_name: Name of the method to call
            *args: Positional arguments for the method
            **kwargs: Keyword arguments for the method

        Returns:
            ProviderResult from whichever provider succeeded
        """
        import time

        start_time = time.time()

        # Try primary first
        if not self._using_fallback:
            try:
                method = getattr(self.primary, method_name)
                result = await method(*args, **kwargs)

                return ProviderResult(
                    success=True,
                    data=result,
                    duration=time.time() - start_time,
                    metadata={"provider": self.primary.name},
                )

            except self.fallback_on_errors as e:
                logger.warning(
                    f"Primary provider {self.primary.name} failed, "
                    f"falling back to {self.fallback.name}: {e}"
                )
                self._using_fallback = True

        # Try fallback
        try:
            method = getattr(self.fallback, method_name)
            result = await method(*args, **kwargs)

            return ProviderResult(
                success=True,
                data=result,
                duration=time.time() - start_time,
                metadata={"provider": self.fallback.name, "used_fallback": True},
            )

        except Exception as e:
            return ProviderResult(
                success=False,
                error=ProviderError(str(e), self.fallback.name),
                duration=time.time() - start_time,
                metadata={"provider": self.fallback.name, "used_fallback": True},
            )

    def reset_to_primary(self) -> None:
        """Reset to try primary provider again."""
        self._using_fallback = False
