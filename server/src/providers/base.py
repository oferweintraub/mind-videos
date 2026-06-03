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


@dataclass
class BatchItemResult(Generic[T]):
    """Result for a single item in a batch operation."""

    index: int
    success: bool
    data: Optional[T] = None
    error: Optional[ProviderError] = None
    attempts: int = 1


@dataclass
class BatchResult(Generic[T]):
    """Result from a batch operation with structured error tracking."""

    items: list[BatchItemResult[T]] = field(default_factory=list)
    total_duration: float = 0.0

    @property
    def successful_items(self) -> list[BatchItemResult[T]]:
        """Get all successful items."""
        return [item for item in self.items if item.success]

    @property
    def failed_items(self) -> list[BatchItemResult[T]]:
        """Get all failed items."""
        return [item for item in self.items if not item.success]

    @property
    def success_count(self) -> int:
        """Count of successful items."""
        return len(self.successful_items)

    @property
    def failure_count(self) -> int:
        """Count of failed items."""
        return len(self.failed_items)

    @property
    def all_successful(self) -> bool:
        """Check if all items succeeded."""
        return self.failure_count == 0

    @property
    def all_failed(self) -> bool:
        """Check if all items failed."""
        return self.success_count == 0

    def get_data(self) -> list[Optional[T]]:
        """Get data from all items (None for failures)."""
        return [item.data for item in self.items]

    def get_successful_data(self) -> list[T]:
        """Get data from successful items only."""
        return [item.data for item in self.successful_items if item.data is not None]

    def get_errors(self) -> list[tuple[int, ProviderError]]:
        """Get all errors with their indices."""
        return [(item.index, item.error) for item in self.failed_items if item.error]


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5  # Failures before opening circuit
    recovery_timeout: float = 60.0  # Seconds before trying again
    half_open_max_calls: int = 3  # Test calls in half-open state


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast, not making calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class TimeoutConfig:
    """Per-operation timeout configuration."""

    default: float = 60.0
    health_check: float = 10.0
    audio_generation: float = 120.0
    image_generation: float = 120.0
    video_generation: float = 300.0  # Video jobs need longer
    video_polling: float = 600.0  # Max time to poll for video completion
    llm_generation: float = 90.0


class BaseProvider(ABC):
    """Abstract base class for all providers."""

    def __init__(
        self,
        name: str,
        api_key: str,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 60.0,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        timeout_config: Optional[TimeoutConfig] = None,
    ):
        self.name = name
        self._api_key = api_key
        self.retry_config = retry_config or RetryConfig()
        self.timeout = timeout
        self.timeout_config = timeout_config or TimeoutConfig(default=timeout)
        self._status = ProviderStatus.AVAILABLE
        self._http_client: Optional[httpx.AsyncClient] = None

        # Circuit breaker state
        self._circuit_config = circuit_breaker_config or CircuitBreakerConfig()
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

    @property
    def status(self) -> ProviderStatus:
        """Get provider status."""
        return self._status

    @property
    def is_available(self) -> bool:
        """Check if provider is available."""
        return self._status != ProviderStatus.UNAVAILABLE

    @property
    def circuit_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self._circuit_state

    def _check_circuit(self) -> bool:
        """Check if circuit allows the call. Returns True if call should proceed."""
        import time

        if self._circuit_state == CircuitState.CLOSED:
            return True

        if self._circuit_state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self._circuit_config.recovery_timeout:
                    logger.info(f"{self.name}: Circuit transitioning to half-open")
                    self._circuit_state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    return True
            return False

        if self._circuit_state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open state
            if self._half_open_calls < self._circuit_config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        return True

    def _record_success(self) -> None:
        """Record a successful call - reset circuit breaker."""
        if self._circuit_state == CircuitState.HALF_OPEN:
            logger.info(f"{self.name}: Circuit closing after successful recovery")
            self._circuit_state = CircuitState.CLOSED
            self._status = ProviderStatus.AVAILABLE

        self._failure_count = 0
        self._last_failure_time = None

    def _record_failure(self) -> None:
        """Record a failed call - potentially open circuit."""
        import time

        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._circuit_state == CircuitState.HALF_OPEN:
            logger.warning(f"{self.name}: Circuit re-opening after failure in half-open state")
            self._circuit_state = CircuitState.OPEN
            self._status = ProviderStatus.UNAVAILABLE
            return

        if self._failure_count >= self._circuit_config.failure_threshold:
            logger.warning(
                f"{self.name}: Circuit opening after {self._failure_count} failures"
            )
            self._circuit_state = CircuitState.OPEN
            self._status = ProviderStatus.UNAVAILABLE
        elif self._failure_count >= self._circuit_config.failure_threshold // 2:
            self._status = ProviderStatus.DEGRADED

    def get_timeout_for_operation(self, operation: str) -> float:
        """Get timeout for a specific operation type."""
        timeouts = {
            "health_check": self.timeout_config.health_check,
            "audio": self.timeout_config.audio_generation,
            "image": self.timeout_config.image_generation,
            "video": self.timeout_config.video_generation,
            "video_poll": self.timeout_config.video_polling,
            "llm": self.timeout_config.llm_generation,
        }
        return timeouts.get(operation, self.timeout_config.default)

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
        """Execute operation with retry logic and circuit breaker."""
        import time

        start_time = time.time()
        last_error: Optional[ProviderError] = None

        # Check circuit breaker
        if not self._check_circuit():
            logger.warning(f"{self.name}: Circuit open, failing fast for {operation_name}")
            return ProviderResult(
                success=False,
                error=ProviderError(
                    f"Circuit breaker open for {self.name}",
                    self.name,
                    recoverable=True,
                ),
                attempts=0,
                duration=time.time() - start_time,
                metadata={"circuit_state": self._circuit_state.value},
            )

        for attempt in range(self.retry_config.max_retries):
            try:
                result = await operation()
                self._record_success()
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
                    self._record_failure()
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

        # All retries exhausted - record failure for circuit breaker
        self._record_failure()

        return ProviderResult(
            success=False,
            error=last_error,
            attempts=self.retry_config.max_retries,
            duration=time.time() - start_time,
            metadata={"circuit_state": self._circuit_state.value},
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
