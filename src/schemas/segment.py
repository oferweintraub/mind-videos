"""Segment schema for individual video segments."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CameraAngle(str, Enum):
    """Camera angle options for scene direction."""

    CLOSE_UP = "close_up"
    MEDIUM = "medium"
    WIDE = "wide"
    OVER_SHOULDER = "over_shoulder"
    LOW_ANGLE = "low_angle"
    HIGH_ANGLE = "high_angle"
    PROFILE = "profile"


class Lighting(str, Enum):
    """Lighting options for scene atmosphere."""

    NATURAL = "natural"
    SOFT = "soft"
    DRAMATIC = "dramatic"
    WARM = "warm"
    COOL = "cool"
    STUDIO = "studio"
    GOLDEN_HOUR = "golden_hour"


class Expression(str, Enum):
    """Facial expression options for character."""

    NEUTRAL = "neutral"
    THOUGHTFUL = "thoughtful"
    CONCERNED = "concerned"
    HOPEFUL = "hopeful"
    DETERMINED = "determined"
    EMPATHETIC = "empathetic"
    PASSIONATE = "passionate"
    CALM = "calm"
    SERIOUS = "serious"


class SceneDefinition(BaseModel):
    """Scene direction for a segment."""

    camera_angle: CameraAngle = Field(
        description="Camera angle for the shot"
    )
    lighting: Lighting = Field(
        description="Lighting setup for the scene"
    )
    expression: Expression = Field(
        description="Character's facial expression"
    )
    setting: str = Field(
        description="Brief description of the background setting",
        max_length=100
    )
    motion_prompt: Optional[str] = Field(
        default=None,
        description="Motion description for video generation (Workflow 2)",
        max_length=200
    )


class Segment(BaseModel):
    """A single segment of the video script."""

    index: int = Field(
        description="Segment index (0-based)",
        ge=0
    )
    text: str = Field(
        description="Hebrew text to be spoken",
        min_length=1,
        max_length=500
    )
    duration_estimate: float = Field(
        description="Estimated duration in seconds",
        ge=3.0,
        le=15.0
    )
    scene: SceneDefinition = Field(
        description="Scene direction for this segment"
    )
    purpose: str = Field(
        description="Brief description of what this segment conveys",
        max_length=150
    )

    # Generated during pipeline execution
    audio_path: Optional[str] = Field(
        default=None,
        description="Path to generated audio file"
    )
    audio_duration: Optional[float] = Field(
        default=None,
        description="Actual audio duration in seconds"
    )
    image_path: Optional[str] = Field(
        default=None,
        description="Path to generated image"
    )
    video_path: Optional[str] = Field(
        default=None,
        description="Path to generated video clip"
    )
    video_duration: Optional[float] = Field(
        default=None,
        description="Actual video duration in seconds"
    )

    class Config:
        use_enum_values = True


class SegmentList(BaseModel):
    """List of segments for Instructor validation."""

    segments: list[Segment] = Field(
        description="List of video segments",
        min_length=4,
        max_length=10
    )

    def total_estimated_duration(self) -> float:
        """Calculate total estimated duration."""
        return sum(s.duration_estimate for s in self.segments)

    def get_segment(self, index: int) -> Optional[Segment]:
        """Get segment by index."""
        for segment in self.segments:
            if segment.index == index:
                return segment
        return None
