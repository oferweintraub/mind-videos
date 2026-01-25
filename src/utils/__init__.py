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
