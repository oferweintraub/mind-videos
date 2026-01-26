"""Utility modules for the Hebrew Democracy Video Pipeline."""

from .ffmpeg import (
    FFmpegError,
    add_fade_effects,
    add_subtitles,
    concatenate_videos,
    extract_thumbnails,
    get_video_info,
    normalize_audio,
    run_ffmpeg,
)
from .image_utils import (
    DEFAULT_PATTERN_5_SEGMENTS,
    PATTERNS,
    apply_segment_pattern,
    get_default_pattern,
    get_image_dimensions,
    resize_image,
    split_mosaic,
)
from .metadata import MetadataTracker
from .video_transitions import (
    TransitionConfig,
    TransitionType,
    concatenate_with_crossfades,
    concatenate_with_smart_transitions,
    crossfade_two_videos,
    detect_scene_changes_by_image,
)
from .audio_utils import (
    get_audio_duration,
    normalize_audio as normalize_audio_file,
    preprocess_for_lipsync,
    resample_audio,
    trim_silence,
)

__all__ = [
    # FFMPEG
    "FFmpegError",
    "run_ffmpeg",
    "get_video_info",
    "concatenate_videos",
    "add_subtitles",
    "extract_thumbnails",
    "add_fade_effects",
    "normalize_audio",
    # Video Transitions
    "TransitionType",
    "TransitionConfig",
    "crossfade_two_videos",
    "concatenate_with_crossfades",
    "concatenate_with_smart_transitions",
    "detect_scene_changes_by_image",
    # Audio Utils
    "normalize_audio_file",
    "trim_silence",
    "resample_audio",
    "preprocess_for_lipsync",
    "get_audio_duration",
    # Image Utils
    "split_mosaic",
    "resize_image",
    "get_image_dimensions",
    "apply_segment_pattern",
    "get_default_pattern",
    "DEFAULT_PATTERN_5_SEGMENTS",
    "PATTERNS",
    # Metadata
    "MetadataTracker",
]
