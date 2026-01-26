"""ElevenLabs audio provider for Hebrew TTS."""

import logging
from pathlib import Path
from typing import Optional

from elevenlabs import AsyncElevenLabs, VoiceSettings

from ..base import (
    AuthenticationError,
    BaseAudioProvider,
    BatchItemResult,
    BatchResult,
    ContentError,
    ProviderError,
    ProviderResult,
    RateLimitError,
    RetryConfig,
)

logger = logging.getLogger(__name__)

# Hebrew-capable voices on ElevenLabs
HEBREW_VOICES = {
    "jessica": "EXAVITQu4vr4xnSDxMaL",  # Female, good for narration
    "adam": "pNInz6obpgDQGcFmaJgB",  # Male, clear pronunciation
    "rachel": "21m00Tcm4TlvDq8ikWAM",  # Female, soft
    "josh": "TxGEqnHWrfWFTfGW9XjX",  # Male, natural
}

# Emotion presets: (stability, style, description)
# Stability: 0.0 = Creative (most expressive), 0.5 = Natural, 1.0 = Robust (most stable)
# Style: 0.0-1.0, higher = more emotional intensity
EMOTION_PRESETS = {
    "neutral": {
        "stability": 0.5,
        "style": 0.0,
        "description": "Calm, neutral delivery",
    },
    "angry": {
        "stability": 0.0,  # Creative/expressive
        "style": 0.9,
        "description": "Frustrated, intense delivery",
    },
    "disappointed": {
        "stability": 0.0,
        "style": 0.6,
        "description": "Let down, somber tone",
    },
    "hopeful": {
        "stability": 0.5,
        "style": 0.5,
        "description": "Optimistic, uplifting tone",
    },
    "determined": {
        "stability": 0.5,
        "style": 0.8,
        "description": "Strong, resolute delivery",
    },
    "sad": {
        "stability": 0.0,
        "style": 0.5,
        "description": "Melancholic, subdued tone",
    },
    "excited": {
        "stability": 0.0,
        "style": 1.0,
        "description": "Energetic, enthusiastic delivery",
    },
    "serious": {
        "stability": 1.0,  # Robust/stable
        "style": 0.4,
        "description": "Grave, authoritative tone",
    },
    "sarcastic": {
        "stability": 0.0,
        "style": 0.7,
        "description": "Ironic, sardonic delivery",
    },
    "empathetic": {
        "stability": 0.5,
        "style": 0.4,
        "description": "Warm, understanding tone",
    },
    "urgent": {
        "stability": 0.0,
        "style": 0.9,
        "description": "Pressing, immediate delivery",
    },
    "cynical": {
        "stability": 0.5,
        "style": 0.6,
        "description": "Skeptical, world-weary tone",
    },
}


class ElevenLabsProvider(BaseAudioProvider):
    """ElevenLabs TTS provider with Hebrew support."""

    # ElevenLabs chunk size limit for multilingual model
    MAX_CHUNK_SIZE = 5000

    def __init__(
        self,
        api_key: str,
        voice_id: str = "EXAVITQu4vr4xnSDxMaL",  # Jessica
        model_id: str = "eleven_v3",  # v3 for better quality
        language_code: str = "he",  # Hebrew
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,  # 0 = neutral, 1 = very expressive
        emotion: Optional[str] = None,  # Emotion preset name
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 60.0,
    ):
        super().__init__(
            name="elevenlabs",
            api_key=api_key,
            retry_config=retry_config,
            timeout=timeout,
        )
        self.voice_id = voice_id
        self.model_id = model_id
        self.language_code = language_code
        self.similarity_boost = similarity_boost
        self._client: Optional[AsyncElevenLabs] = None

        # Apply emotion preset if specified, otherwise use direct values
        if emotion and emotion in EMOTION_PRESETS:
            preset = EMOTION_PRESETS[emotion]
            self.stability = preset["stability"]
            self.style = preset["style"]
            self.emotion = emotion
            logger.info(f"Using emotion preset '{emotion}': {preset['description']}")
        else:
            self.stability = stability
            self.style = style
            self.emotion = None

    @property
    def client(self) -> AsyncElevenLabs:
        """Get or create ElevenLabs client."""
        if self._client is None:
            self._client = AsyncElevenLabs(api_key=self._api_key)
        return self._client

    async def health_check(self) -> bool:
        """Check if ElevenLabs API is accessible."""
        try:
            # Try to get user info to verify API key
            user = await self.client.user.get()
            return user is not None
        except Exception as e:
            logger.error(f"ElevenLabs health check failed: {e}")
            return False

    async def get_available_voices(self) -> list[dict]:
        """Get list of available voices."""
        try:
            voices = await self.client.voices.get_all()
            return [
                {
                    "voice_id": v.voice_id,
                    "name": v.name,
                    "category": v.category,
                    "labels": v.labels,
                }
                for v in voices.voices
            ]
        except Exception as e:
            logger.error(f"Failed to get voices: {e}")
            raise ProviderError(f"Failed to get voices: {e}", self.name)

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks for long content.

        Hebrew text is split on sentence boundaries (periods, question marks,
        exclamation marks) to maintain natural speech flow.
        """
        if len(text) <= self.MAX_CHUNK_SIZE:
            return [text]

        chunks = []
        current_chunk = ""

        # Split on sentence boundaries
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= self.MAX_CHUNK_SIZE:
                current_chunk += (" " + sentence) if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _handle_api_error(self, error: Exception) -> None:
        """Convert API errors to provider errors."""
        error_str = str(error).lower()

        if "401" in error_str or "unauthorized" in error_str or "invalid api key" in error_str:
            raise AuthenticationError(
                "Invalid ElevenLabs API key",
                self.name,
            )

        if "429" in error_str or "rate limit" in error_str:
            raise RateLimitError(
                "ElevenLabs rate limit exceeded",
                self.name,
                retry_after=60.0,  # Default retry after 1 minute
            )

        if "content" in error_str or "inappropriate" in error_str:
            raise ContentError(
                f"Content rejected by ElevenLabs: {error}",
                self.name,
            )

        raise ProviderError(str(error), self.name)

    async def _generate_chunk(
        self,
        text: str,
        voice_id: str,
        stability: Optional[float] = None,
        style: Optional[float] = None,
    ) -> bytes:
        """Generate audio for a single text chunk.

        Args:
            text: Text to convert to speech
            voice_id: ElevenLabs voice ID
            stability: Override stability (0-1, lower = more expressive)
            style: Override style (0-1, higher = more emotional)
        """
        try:
            voice_settings = VoiceSettings(
                stability=stability if stability is not None else self.stability,
                similarity_boost=self.similarity_boost,
                style=style if style is not None else self.style,
            )

            # convert() returns AsyncIterator directly (not a coroutine)
            audio_generator = self.client.text_to_speech.convert(
                voice_id=voice_id,
                model_id=self.model_id,
                text=text,
                voice_settings=voice_settings,
                language_code=self.language_code,  # Specify Hebrew
            )

            # Collect all audio chunks
            audio_chunks = []
            async for chunk in audio_generator:
                audio_chunks.append(chunk)

            return b"".join(audio_chunks)

        except Exception as e:
            self._handle_api_error(e)

    def _estimate_duration(self, text: str) -> float:
        """Estimate audio duration from text length.

        Hebrew speech averages ~3-4 words per second, roughly 15 chars/second.
        """
        # Remove spaces for character count
        char_count = len(text.replace(" ", ""))
        # Estimate ~15 characters per second for Hebrew
        return char_count / 15.0

    def _get_actual_duration(self, audio_bytes: bytes) -> float:
        """Get actual duration from MP3 audio bytes.

        Uses mutagen for accurate duration calculation.
        """
        try:
            from io import BytesIO
            from mutagen.mp3 import MP3

            audio_file = BytesIO(audio_bytes)
            audio = MP3(audio_file)
            return audio.info.length
        except Exception:
            # Fallback: estimate from file size
            # MP3 at 128kbps = ~16KB per second
            return len(audio_bytes) / 16000

    async def generate_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        output_path: Optional[Path] = None,
        emotion: Optional[str] = None,
        stability: Optional[float] = None,
        style: Optional[float] = None,
        **kwargs,
    ) -> tuple[bytes, float]:
        """Generate Hebrew speech from text with optional emotion control.

        Args:
            text: Hebrew text to convert to speech
            voice_id: Optional voice ID (defaults to configured voice)
            output_path: Optional path to save the audio file
            emotion: Emotion preset name (angry, disappointed, hopeful, etc.)
                     Overrides stability and style settings.
            stability: Direct stability value (0-1, lower = more expressive)
            style: Direct style value (0-1, higher = more emotional)
            **kwargs: Additional parameters (unused)

        Returns:
            Tuple of (audio_bytes, duration_seconds)

        Available emotion presets:
            - neutral: Calm, neutral delivery
            - angry: Frustrated, intense delivery
            - disappointed: Let down, somber tone
            - hopeful: Optimistic, uplifting tone
            - determined: Strong, resolute delivery
            - sad: Melancholic, subdued tone
            - excited: Energetic, enthusiastic delivery
            - serious: Grave, authoritative tone
            - sarcastic: Ironic, sardonic delivery
            - empathetic: Warm, understanding tone
            - urgent: Pressing, immediate delivery
            - cynical: Skeptical, world-weary tone
        """
        voice_id = voice_id or self.voice_id

        # Validate text
        if not text or not text.strip():
            raise ProviderError("Empty text provided", self.name, recoverable=False)

        # Apply emotion preset if specified
        if emotion and emotion in EMOTION_PRESETS:
            preset = EMOTION_PRESETS[emotion]
            stability = preset["stability"]
            style = preset["style"]
            logger.info(f"Generating speech with emotion '{emotion}': {preset['description']}")

        # Clean text for Hebrew (remove extra whitespace)
        text = " ".join(text.split())

        # Check if text needs chunking
        chunks = self._chunk_text(text)

        if len(chunks) == 1:
            # Single chunk - simple case
            async def _generate():
                return await self._generate_chunk(text, voice_id, stability, style)

            result = await self._retry_operation(_generate, "generate_speech")

            if not result.success:
                raise result.error or ProviderError("Speech generation failed", self.name)

            audio_bytes = result.data

        else:
            # Multiple chunks - concatenate audio
            logger.info(f"Text exceeds max length, splitting into {len(chunks)} chunks")

            audio_parts = []
            for i, chunk in enumerate(chunks):
                async def _generate_chunk_wrapper():
                    return await self._generate_chunk(chunk, voice_id, stability, style)

                result = await self._retry_operation(
                    _generate_chunk_wrapper,
                    f"generate_speech_chunk_{i+1}"
                )

                if not result.success:
                    raise result.error or ProviderError(
                        f"Speech generation failed for chunk {i+1}",
                        self.name
                    )

                audio_parts.append(result.data)

            # Concatenate audio parts
            audio_bytes = self._concatenate_audio(audio_parts)

        # Get actual duration
        duration = self._get_actual_duration(audio_bytes)

        # Save to file if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_bytes)
            logger.info(f"Audio saved to {output_path} ({duration:.2f}s)")

        return audio_bytes, duration

    def _concatenate_audio(self, audio_parts: list[bytes]) -> bytes:
        """Concatenate multiple MP3 audio parts.

        For simplicity, we concatenate the raw bytes. For production,
        consider using pydub or ffmpeg for proper concatenation.
        """
        # Simple concatenation works for MP3 files from the same source
        return b"".join(audio_parts)

    async def generate_speech_with_result(
        self,
        text: str,
        voice_id: Optional[str] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> ProviderResult[tuple[bytes, float]]:
        """Generate speech and return full result with metadata.

        Args:
            text: Hebrew text to convert to speech
            voice_id: Optional voice ID
            output_path: Optional path to save audio
            **kwargs: Additional parameters

        Returns:
            ProviderResult containing (audio_bytes, duration) tuple
        """
        async def _generate():
            return await self.generate_speech(text, voice_id, output_path, **kwargs)

        result = await self._retry_operation(_generate, "generate_speech")

        if result.success:
            audio_bytes, duration = result.data
            result.metadata = {
                "text_length": len(text),
                "duration": duration,
                "voice_id": voice_id or self.voice_id,
                "model_id": self.model_id,
                "output_path": str(output_path) if output_path else None,
            }

        return result

    async def close(self) -> None:
        """Close the provider and cleanup resources."""
        await super().close()
        self._client = None

    async def generate_batch(
        self,
        texts: list[str],
        output_dir: Path,
        voice_id: Optional[str] = None,
        fail_fast: bool = False,
        **kwargs,
    ) -> BatchResult[tuple[bytes, float]]:
        """Generate speech for multiple texts with structured error tracking.

        Args:
            texts: List of texts to convert to speech
            output_dir: Directory to save audio files
            voice_id: Optional voice ID (defaults to configured voice)
            fail_fast: If True, stop on first failure
            **kwargs: Additional parameters

        Returns:
            BatchResult with structured success/failure tracking
        """
        import time

        start_time = time.time()
        output_dir.mkdir(parents=True, exist_ok=True)
        batch_result = BatchResult[tuple[bytes, float]]()

        for i, text in enumerate(texts):
            output_path = output_dir / f"audio_{i:02d}.mp3"

            try:
                audio_bytes, duration = await self.generate_speech(
                    text=text,
                    voice_id=voice_id,
                    output_path=output_path,
                    **kwargs,
                )

                batch_result.items.append(
                    BatchItemResult(
                        index=i,
                        success=True,
                        data=(audio_bytes, duration),
                    )
                )
                logger.info(f"Generated audio {i+1}/{len(texts)} ({duration:.2f}s)")

            except ProviderError as e:
                logger.error(f"Failed to generate audio {i+1}: {e}")
                batch_result.items.append(
                    BatchItemResult(
                        index=i,
                        success=False,
                        error=e,
                    )
                )
                if fail_fast:
                    logger.warning(f"Batch generation stopped at audio {i+1} due to fail_fast")
                    break

            except Exception as e:
                logger.error(f"Unexpected error generating audio {i+1}: {e}")
                batch_result.items.append(
                    BatchItemResult(
                        index=i,
                        success=False,
                        error=ProviderError(str(e), self.name),
                    )
                )
                if fail_fast:
                    logger.warning(f"Batch generation stopped at audio {i+1} due to fail_fast")
                    break

        batch_result.total_duration = time.time() - start_time

        # Log summary
        total_audio_duration = sum(
            item.data[1] for item in batch_result.successful_items if item.data
        )
        logger.info(
            f"Batch complete: {batch_result.success_count}/{len(texts)} succeeded, "
            f"total audio: {total_audio_duration:.2f}s, "
            f"processing time: {batch_result.total_duration:.2f}s"
        )

        return batch_result
