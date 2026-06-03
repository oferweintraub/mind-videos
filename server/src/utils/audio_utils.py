"""Audio preprocessing utilities for improved lip-sync quality."""

import asyncio
import io
import logging
import struct
import wave
from pathlib import Path
from typing import Optional, Union

from .ffmpeg import FFmpegError, run_ffmpeg

logger = logging.getLogger(__name__)


async def normalize_audio(
    audio_input: Union[bytes, Path],
    output_path: Optional[Path] = None,
    target_lufs: float = -16.0,
    true_peak: float = -1.5,
    loudness_range: float = 11.0,
) -> bytes:
    """Normalize audio to consistent loudness using EBU R128 standard.

    This helps improve lip-sync quality by ensuring consistent audio levels.

    Args:
        audio_input: Audio bytes or path to audio file
        output_path: Optional path to save normalized audio
        target_lufs: Target integrated loudness in LUFS (default: -16)
        true_peak: Maximum true peak in dBTP (default: -1.5)
        loudness_range: Target loudness range in LU (default: 11)

    Returns:
        Normalized audio bytes
    """
    # Handle input
    if isinstance(audio_input, bytes):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_input)
            input_path = Path(f.name)
        cleanup_input = True
    else:
        input_path = audio_input
        cleanup_input = False

    # Setup output
    if output_path is None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            output_path = Path(f.name)
        cleanup_output = True
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cleanup_output = False

    try:
        # Use loudnorm filter for EBU R128 normalization
        args = [
            "-i", str(input_path),
            "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={loudness_range}",
            "-ar", "44100",  # Consistent sample rate
            "-ac", "1",  # Mono for lip-sync
            str(output_path),
        ]

        await run_ffmpeg(args, timeout=60)

        # Read output
        result = output_path.read_bytes()

        logger.debug(f"Normalized audio to {target_lufs} LUFS")

        return result

    finally:
        if cleanup_input:
            input_path.unlink(missing_ok=True)
        if cleanup_output and output_path.exists():
            output_path.unlink(missing_ok=True)


async def trim_silence(
    audio_input: Union[bytes, Path],
    output_path: Optional[Path] = None,
    threshold_db: float = -50.0,
    min_silence_duration: float = 0.1,
    padding_start: float = 0.05,
    padding_end: float = 0.1,
) -> bytes:
    """Trim silence from start and end of audio.

    This helps improve lip-sync by removing dead air at clip boundaries.

    Args:
        audio_input: Audio bytes or path to audio file
        output_path: Optional path to save trimmed audio
        threshold_db: Silence threshold in dB (default: -50)
        min_silence_duration: Minimum silence duration to detect (default: 0.1s)
        padding_start: Padding to keep at start (default: 0.05s)
        padding_end: Padding to keep at end (default: 0.1s)

    Returns:
        Trimmed audio bytes
    """
    # Handle input
    if isinstance(audio_input, bytes):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_input)
            input_path = Path(f.name)
        cleanup_input = True
    else:
        input_path = audio_input
        cleanup_input = False

    # Setup output
    if output_path is None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            output_path = Path(f.name)
        cleanup_output = True
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cleanup_output = False

    try:
        # Use silenceremove filter to trim silence from start and end
        # start_periods=1 means detect one period of silence at start
        # stop_periods=-1 means detect silence at end (all remaining silence)
        filter_complex = (
            f"silenceremove=start_periods=1:start_duration={min_silence_duration}:"
            f"start_threshold={threshold_db}dB:"
            f"stop_periods=-1:stop_duration={min_silence_duration}:"
            f"stop_threshold={threshold_db}dB,"
            f"apad=pad_dur={padding_end},"
            f"adelay={int(padding_start * 1000)}|{int(padding_start * 1000)}"
        )

        args = [
            "-i", str(input_path),
            "-af", filter_complex,
            str(output_path),
        ]

        await run_ffmpeg(args, timeout=60)

        result = output_path.read_bytes()

        logger.debug("Trimmed silence from audio")

        return result

    finally:
        if cleanup_input:
            input_path.unlink(missing_ok=True)
        if cleanup_output and output_path.exists():
            output_path.unlink(missing_ok=True)


async def resample_audio(
    audio_input: Union[bytes, Path],
    output_path: Optional[Path] = None,
    sample_rate: int = 44100,
    channels: int = 1,
    format: str = "mp3",
) -> bytes:
    """Resample audio to consistent sample rate and channels.

    Args:
        audio_input: Audio bytes or path to audio file
        output_path: Optional path to save resampled audio
        sample_rate: Target sample rate in Hz (default: 44100)
        channels: Number of channels (default: 1 for mono)
        format: Output format (default: mp3)

    Returns:
        Resampled audio bytes
    """
    # Handle input
    if isinstance(audio_input, bytes):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_input)
            input_path = Path(f.name)
        cleanup_input = True
    else:
        input_path = audio_input
        cleanup_input = False

    # Setup output
    if output_path is None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as f:
            output_path = Path(f.name)
        cleanup_output = True
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cleanup_output = False

    try:
        args = [
            "-i", str(input_path),
            "-ar", str(sample_rate),
            "-ac", str(channels),
            str(output_path),
        ]

        await run_ffmpeg(args, timeout=60)

        result = output_path.read_bytes()

        logger.debug(f"Resampled audio to {sample_rate}Hz, {channels}ch")

        return result

    finally:
        if cleanup_input:
            input_path.unlink(missing_ok=True)
        if cleanup_output and output_path.exists():
            output_path.unlink(missing_ok=True)


async def preprocess_for_lipsync(
    audio_input: Union[bytes, Path],
    output_path: Optional[Path] = None,
    normalize: bool = True,
    trim: bool = True,
    target_lufs: float = -16.0,
    sample_rate: int = 44100,
) -> bytes:
    """Full preprocessing pipeline for optimal lip-sync quality.

    Applies normalization, silence trimming, and resampling in optimal order.

    Args:
        audio_input: Audio bytes or path to audio file
        output_path: Optional path to save processed audio
        normalize: Whether to apply loudness normalization (default: True)
        trim: Whether to trim silence (default: True)
        target_lufs: Target loudness in LUFS (default: -16)
        sample_rate: Target sample rate (default: 44100)

    Returns:
        Preprocessed audio bytes
    """
    current_audio = audio_input

    # Step 1: Resample to consistent format
    current_audio = await resample_audio(
        current_audio,
        sample_rate=sample_rate,
        channels=1,  # Mono for lip-sync
    )

    # Step 2: Trim silence (if enabled)
    if trim:
        current_audio = await trim_silence(current_audio)

    # Step 3: Normalize loudness (if enabled)
    if normalize:
        current_audio = await normalize_audio(
            current_audio,
            output_path=output_path,
            target_lufs=target_lufs,
        )
    elif output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(current_audio)

    logger.info(
        f"Preprocessed audio for lip-sync "
        f"(normalize={normalize}, trim={trim}, rate={sample_rate}Hz)"
    )

    return current_audio


async def get_audio_duration(audio_input: Union[bytes, Path]) -> float:
    """Get duration of an audio file.

    Args:
        audio_input: Audio bytes or path to audio file

    Returns:
        Duration in seconds
    """
    # Handle input
    if isinstance(audio_input, bytes):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_input)
            input_path = Path(f.name)
        cleanup_input = True
    else:
        input_path = audio_input
        cleanup_input = False

    try:
        import json

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(input_path),
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await process.communicate()

        if process.returncode != 0:
            raise FFmpegError(f"ffprobe failed for audio")

        data = json.loads(stdout.decode())
        return float(data.get("format", {}).get("duration", 0))

    finally:
        if cleanup_input:
            input_path.unlink(missing_ok=True)
