"""Video transition utilities for crossfade effects between segments."""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from .ffmpeg import FFmpegError, get_video_info, run_ffmpeg

logger = logging.getLogger(__name__)


class TransitionType(str, Enum):
    """Available FFmpeg xfade transition types."""

    FADE = "fade"  # Standard crossfade - good for same-scene cuts
    DISSOLVE = "dissolve"  # Smooth blend - good for scene changes
    FADEBLACK = "fadeblack"  # Fade through black - dramatic scene changes
    FADEWHITE = "fadewhite"  # Fade through white - dream sequences
    WIPELEFT = "wipeleft"  # Wipe from right to left - editorial style
    WIPERIGHT = "wiperight"  # Wipe from left to right
    WIPEUP = "wipeup"  # Wipe from bottom to top
    WIPEDOWN = "wipedown"  # Wipe from top to bottom
    SLIDELEFT = "slideleft"  # Slide transition
    SLIDERIGHT = "slideright"
    CIRCLECROP = "circlecrop"  # Circular reveal
    SMOOTHLEFT = "smoothleft"  # Smooth slide
    SMOOTHRIGHT = "smoothright"


@dataclass
class TransitionConfig:
    """Configuration for a single transition between segments."""

    type: TransitionType = TransitionType.DISSOLVE
    duration: float = 0.5  # Duration in seconds for video transition

    # Audio transition settings
    audio_crossfade: bool = False  # If True, overlap audio; if False, use gap with fades
    audio_gap: float = 0.5  # Total silence gap between segments (split evenly as fade out/in)
    audio_fade_duration: float = 0.25  # Duration of fade out/in on each side
    audio_curve: str = "exp"  # Fade curve (exp, log, tri, lin)


@dataclass
class SegmentTransition:
    """Defines transition between two specific segments."""

    segment_index: int  # Index of the first segment (transition happens after this)
    config: TransitionConfig


async def get_segment_duration(video_path: Path) -> float:
    """Get the duration of a video segment.

    Args:
        video_path: Path to video file

    Returns:
        Duration in seconds
    """
    info = await get_video_info(video_path)
    return info.get("duration", 0.0)


async def crossfade_two_videos(
    video1_path: Path,
    video2_path: Path,
    output_path: Path,
    transition: TransitionConfig,
) -> Path:
    """Crossfade two videos together.

    When audio_crossfade=False (default), this creates a sequential transition:
    1. Segment 1 plays fully with speech
    2. Segment 1 fades out (video + audio)
    3. Segment 2 fades in (video + audio)
    4. Segment 2 plays fully with speech

    This ensures speech never overlaps.

    Args:
        video1_path: First video path
        video2_path: Second video path
        output_path: Output video path
        transition: Transition configuration

    Returns:
        Path to output video
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    duration1 = await get_segment_duration(video1_path)
    duration2 = await get_segment_duration(video2_path)

    if transition.audio_crossfade:
        # Original xfade behavior - videos overlap, audio overlaps
        offset = max(0, duration1 - transition.duration)

        video_filter = (
            f"[0:v][1:v]xfade=transition={transition.type.value}:"
            f"duration={transition.duration}:offset={offset}[v]"
        )
        audio_filter = (
            f"[0:a][1:a]acrossfade=d={transition.duration}:"
            f"c1={transition.audio_curve}:c2={transition.audio_curve}[a]"
        )
        filter_complex = f"{video_filter};{audio_filter}"
    else:
        # Sequential transition - NO content overlap, NO audio cutting
        # Speech plays FULLY, then visual transition, then next speech
        fade_dur = transition.audio_fade_duration
        gap = transition.audio_gap  # Gap between segments

        # Get video properties for black frame generation
        info1 = await get_video_info(video1_path)
        width = info1.get('width', 864)
        height = info1.get('height', 480)
        fps = info1.get('fps', 25)

        # Very short video fade (just a few frames)
        video_fade_dur = 0.15

        filter_complex = (
            # Video 1: fade to black at the very end
            f"[0:v]fade=t=out:st={duration1 - video_fade_dur}:d={video_fade_dur}[v0];"
            # Generate black frames for the gap
            f"color=c=black:s={width}x{height}:r={fps}:d={gap}[black];"
            # Video 2: fade in from black at the start
            f"[1:v]fade=t=in:st=0:d={video_fade_dur}[v1];"
            # Concatenate: video1 + black gap + video2
            f"[v0][black][v1]concat=n=3:v=1:a=0[v];"
            # Audio 1: full audio
            f"[0:a]anull[a0];"
            # Generate silence for the gap
            f"aevalsrc=0:d={gap}[silence];"
            # Audio 2: full audio
            f"[1:a]anull[a1];"
            # Concatenate: audio1 + silence + audio2
            f"[a0][silence][a1]concat=n=3:v=0:a=1[a]"
        )

    args = [
        "-i", str(video1_path),
        "-i", str(video2_path),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",  # QuickTime compatibility
        "-profile:v", "high",
        "-level", "4.0",
        "-movflags", "+faststart",  # Enable streaming/QuickTime playback
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path),
    ]

    await run_ffmpeg(args, timeout=300)

    logger.debug(
        f"Transitioned {video1_path.name} + {video2_path.name} "
        f"with {transition.duration}s fade ({transition.type.value})"
    )

    return output_path


async def concatenate_with_crossfades(
    video_paths: list[Path],
    output_path: Path,
    transitions: Optional[list[TransitionConfig]] = None,
    default_transition: Optional[TransitionConfig] = None,
) -> Path:
    """Concatenate multiple videos with crossfade transitions.

    This function chains crossfades efficiently by processing pairs sequentially.

    Args:
        video_paths: List of video paths in order
        output_path: Output video path
        transitions: List of transition configs (one per pair). If None or shorter
                     than needed, uses default_transition for remaining.
        default_transition: Default transition to use when not specified.
                           Defaults to 0.5s dissolve with audio crossfade.

    Returns:
        Path to concatenated video
    """
    if not video_paths:
        raise ValueError("No video paths provided")

    if len(video_paths) == 1:
        # Just copy the single file
        import shutil
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(video_paths[0], output_path)
        return output_path

    # Setup defaults
    if default_transition is None:
        default_transition = TransitionConfig(
            type=TransitionType.DISSOLVE,
            duration=0.5,
            audio_crossfade=True,
        )

    # Ensure we have a transition config for each pair
    n_transitions = len(video_paths) - 1
    if transitions is None:
        transitions = [default_transition] * n_transitions
    else:
        # Extend with default if not enough
        while len(transitions) < n_transitions:
            transitions.append(default_transition)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_path.parent / "_temp_transitions"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Chain crossfades
        current_video = video_paths[0]

        for i in range(n_transitions):
            next_video = video_paths[i + 1]
            transition = transitions[i]

            # Determine output path
            if i == n_transitions - 1:
                # Final output
                temp_output = output_path
            else:
                # Intermediate file
                temp_output = temp_dir / f"temp_{i:02d}.mp4"

            await crossfade_two_videos(
                video1_path=current_video,
                video2_path=next_video,
                output_path=temp_output,
                transition=transition,
            )

            current_video = temp_output

        logger.info(
            f"Concatenated {len(video_paths)} videos with crossfade transitions"
        )

        return output_path

    finally:
        # Cleanup temp files
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


async def concatenate_with_smart_transitions(
    video_paths: list[Path],
    output_path: Path,
    same_scene_indices: Optional[set[int]] = None,
    same_scene_transition: Optional[TransitionConfig] = None,
    scene_change_transition: Optional[TransitionConfig] = None,
) -> Path:
    """Concatenate videos with different transitions for same-scene vs scene changes.

    This allows shorter, subtler transitions between cuts in the same scene,
    and longer, more noticeable transitions for actual scene changes.

    Args:
        video_paths: List of video paths in order
        output_path: Output video path
        same_scene_indices: Set of segment indices where the next segment is the
                           same scene (e.g., {0, 1, 3} means segments 0->1, 1->2,
                           and 3->4 are same-scene cuts). If None, all are treated
                           as scene changes.
        same_scene_transition: Transition for same-scene cuts (default: 0.25s fade)
        scene_change_transition: Transition for scene changes (default: 0.5s dissolve)

    Returns:
        Path to concatenated video
    """
    if same_scene_indices is None:
        same_scene_indices = set()

    if same_scene_transition is None:
        same_scene_transition = TransitionConfig(
            type=TransitionType.FADE,
            duration=0.25,
            audio_crossfade=True,
        )

    if scene_change_transition is None:
        scene_change_transition = TransitionConfig(
            type=TransitionType.DISSOLVE,
            duration=0.5,
            audio_crossfade=True,
        )

    # Build transition list based on scene info
    transitions = []
    for i in range(len(video_paths) - 1):
        if i in same_scene_indices:
            transitions.append(same_scene_transition)
        else:
            transitions.append(scene_change_transition)

    return await concatenate_with_crossfades(
        video_paths=video_paths,
        output_path=output_path,
        transitions=transitions,
    )


def detect_scene_changes_by_image(
    image_paths: list[Optional[str]],
) -> set[int]:
    """Detect same-scene segments based on image path patterns.

    Segments using the same image (reuse pattern) are considered same-scene.

    Args:
        image_paths: List of image paths for each segment (can contain None)

    Returns:
        Set of indices where segment[i] and segment[i+1] are same scene
    """
    same_scene = set()

    for i in range(len(image_paths) - 1):
        path1 = image_paths[i]
        path2 = image_paths[i + 1]

        # If both paths exist and are the same, it's a same-scene cut
        if path1 and path2 and path1 == path2:
            same_scene.add(i)

    return same_scene
