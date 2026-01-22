"""FFMPEG utilities for video processing."""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FFmpegError(Exception):
    """FFMPEG operation error."""

    def __init__(self, message: str, stderr: Optional[str] = None):
        super().__init__(message)
        self.stderr = stderr


async def run_ffmpeg(
    args: list[str],
    timeout: int = 300,
) -> tuple[str, str]:
    """Run an FFMPEG command asynchronously.

    Args:
        args: FFMPEG command arguments (without 'ffmpeg' prefix)
        timeout: Timeout in seconds

    Returns:
        Tuple of (stdout, stderr)

    Raises:
        FFmpegError: If command fails
    """
    cmd = ["ffmpeg", "-y", "-hide_banner"] + args

    logger.debug(f"Running: {' '.join(cmd)}")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        process.kill()
        raise FFmpegError(f"FFMPEG timed out after {timeout}s")

    stdout_str = stdout.decode("utf-8", errors="replace")
    stderr_str = stderr.decode("utf-8", errors="replace")

    if process.returncode != 0:
        raise FFmpegError(
            f"FFMPEG failed with code {process.returncode}",
            stderr_str,
        )

    return stdout_str, stderr_str


def run_ffmpeg_sync(
    args: list[str],
    timeout: int = 300,
) -> tuple[str, str]:
    """Run an FFMPEG command synchronously.

    Args:
        args: FFMPEG command arguments (without 'ffmpeg' prefix)
        timeout: Timeout in seconds

    Returns:
        Tuple of (stdout, stderr)
    """
    cmd = ["ffmpeg", "-y", "-hide_banner"] + args

    logger.debug(f"Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
    )

    stdout_str = result.stdout.decode("utf-8", errors="replace")
    stderr_str = result.stderr.decode("utf-8", errors="replace")

    if result.returncode != 0:
        raise FFmpegError(
            f"FFMPEG failed with code {result.returncode}",
            stderr_str,
        )

    return stdout_str, stderr_str


async def get_video_info(video_path: Path) -> dict:
    """Get video file information using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Dictionary with video info (duration, width, height, etc.)
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise FFmpegError(f"ffprobe failed for {video_path}")

    import json
    data = json.loads(stdout.decode())

    # Extract useful info
    info = {
        "duration": float(data.get("format", {}).get("duration", 0)),
        "format": data.get("format", {}).get("format_name", ""),
    }

    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            info["width"] = stream.get("width")
            info["height"] = stream.get("height")
            info["fps"] = eval(stream.get("r_frame_rate", "0/1")) if "/" in stream.get("r_frame_rate", "") else 0
            info["video_codec"] = stream.get("codec_name")
        elif stream.get("codec_type") == "audio":
            info["audio_codec"] = stream.get("codec_name")
            info["sample_rate"] = stream.get("sample_rate")

    return info


async def concatenate_videos(
    video_paths: list[Path],
    output_path: Path,
    transition: Optional[str] = None,
    transition_duration: float = 0.5,
) -> Path:
    """Concatenate multiple video files.

    Args:
        video_paths: List of video file paths in order
        output_path: Path for output video
        transition: Optional transition type (fade, dissolve)
        transition_duration: Duration of transition in seconds

    Returns:
        Path to concatenated video
    """
    if not video_paths:
        raise ValueError("No video paths provided")

    if len(video_paths) == 1:
        # Just copy the single file
        import shutil
        shutil.copy(video_paths[0], output_path)
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if transition:
        # Use filter_complex for transitions
        return await _concatenate_with_transitions(
            video_paths, output_path, transition, transition_duration
        )

    # Simple concatenation using concat demuxer
    concat_file = output_path.parent / "concat_list.txt"

    with open(concat_file, "w") as f:
        for path in video_paths:
            f.write(f"file '{path.absolute()}'\n")

    args = [
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(output_path),
    ]

    await run_ffmpeg(args)

    # Clean up concat file
    concat_file.unlink()

    logger.info(f"Concatenated {len(video_paths)} videos to {output_path}")

    return output_path


async def _concatenate_with_transitions(
    video_paths: list[Path],
    output_path: Path,
    transition: str,
    transition_duration: float,
) -> Path:
    """Concatenate videos with transitions using filter_complex."""
    inputs = []
    for i, path in enumerate(video_paths):
        inputs.extend(["-i", str(path)])

    # Build filter complex
    filter_parts = []
    n = len(video_paths)

    # Get durations for offset calculation
    durations = []
    for path in video_paths:
        info = await get_video_info(path)
        durations.append(info["duration"])

    if transition == "fade":
        # Crossfade between clips
        prev_output = "0:v"

        for i in range(1, n):
            offset = sum(durations[:i]) - (i * transition_duration)

            filter_parts.append(
                f"[{prev_output}][{i}:v]xfade=transition=fade:"
                f"duration={transition_duration}:offset={offset}[v{i}]"
            )
            prev_output = f"v{i}"

        # Handle audio
        audio_filter = "".join([f"[{i}:a]" for i in range(n)])
        filter_parts.append(f"{audio_filter}concat=n={n}:v=0:a=1[a]")

        args = inputs + [
            "-filter_complex",
            ";".join(filter_parts),
            "-map", f"[v{n-1}]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-c:a", "aac",
            str(output_path),
        ]

    else:
        # Default to simple concat
        return await concatenate_videos(video_paths, output_path)

    await run_ffmpeg(args, timeout=600)

    logger.info(f"Concatenated {n} videos with {transition} transition")

    return output_path


async def add_subtitles(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    burn_in: bool = True,
) -> Path:
    """Add subtitles to a video.

    Args:
        video_path: Input video path
        subtitle_path: Path to SRT or ASS subtitle file
        output_path: Output video path
        burn_in: If True, burn subtitles into video; if False, add as stream

    Returns:
        Path to output video
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if burn_in:
        # Burn subtitles into video using subtitles filter
        escaped_path = str(subtitle_path).replace(":", "\\:").replace("\\", "/")

        args = [
            "-i", str(video_path),
            "-vf", f"subtitles='{escaped_path}'",
            "-c:a", "copy",
            str(output_path),
        ]

    else:
        # Add as separate stream
        args = [
            "-i", str(video_path),
            "-i", str(subtitle_path),
            "-c", "copy",
            "-c:s", "mov_text",
            str(output_path),
        ]

    await run_ffmpeg(args)

    logger.info(f"Added subtitles to video: {output_path}")

    return output_path


async def extract_thumbnails(
    video_path: Path,
    output_dir: Path,
    count: int = 2,
    timestamps: Optional[list[float]] = None,
) -> list[Path]:
    """Extract thumbnail images from video.

    Args:
        video_path: Input video path
        output_dir: Directory for thumbnails
        count: Number of thumbnails to extract
        timestamps: Specific timestamps in seconds (optional)

    Returns:
        List of thumbnail paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get video duration
    info = await get_video_info(video_path)
    duration = info["duration"]

    # Calculate timestamps if not provided
    if timestamps is None:
        # Distribute evenly, avoiding very start and end
        start = duration * 0.1
        end = duration * 0.9
        step = (end - start) / (count - 1) if count > 1 else 0
        timestamps = [start + i * step for i in range(count)]

    thumbnails = []

    for i, ts in enumerate(timestamps):
        output_path = output_dir / f"thumbnail_{i:02d}.jpg"

        args = [
            "-ss", str(ts),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(output_path),
        ]

        await run_ffmpeg(args)
        thumbnails.append(output_path)

    logger.info(f"Extracted {len(thumbnails)} thumbnails from {video_path}")

    return thumbnails


async def add_fade_effects(
    video_path: Path,
    output_path: Path,
    fade_in: float = 0.5,
    fade_out: float = 0.5,
) -> Path:
    """Add fade in/out effects to video.

    Args:
        video_path: Input video path
        output_path: Output video path
        fade_in: Fade in duration in seconds
        fade_out: Fade out duration in seconds

    Returns:
        Path to output video
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get duration for fade out offset
    info = await get_video_info(video_path)
    duration = info["duration"]

    fade_out_start = duration - fade_out

    video_filter = f"fade=t=in:st=0:d={fade_in},fade=t=out:st={fade_out_start}:d={fade_out}"
    audio_filter = f"afade=t=in:st=0:d={fade_in},afade=t=out:st={fade_out_start}:d={fade_out}"

    args = [
        "-i", str(video_path),
        "-vf", video_filter,
        "-af", audio_filter,
        "-c:v", "libx264",
        "-c:a", "aac",
        str(output_path),
    ]

    await run_ffmpeg(args)

    logger.info(f"Added fade effects to video: {output_path}")

    return output_path


async def normalize_audio(
    video_path: Path,
    output_path: Path,
    target_loudness: float = -16.0,
) -> Path:
    """Normalize audio levels in video.

    Args:
        video_path: Input video path
        output_path: Output video path
        target_loudness: Target loudness in LUFS

    Returns:
        Path to output video
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use loudnorm filter for EBU R128 normalization
    args = [
        "-i", str(video_path),
        "-af", f"loudnorm=I={target_loudness}:TP=-1.5:LRA=11",
        "-c:v", "copy",
        "-c:a", "aac",
        str(output_path),
    ]

    await run_ffmpeg(args)

    logger.info(f"Normalized audio in video: {output_path}")

    return output_path
