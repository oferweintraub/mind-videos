"""Script schema for full video scripts."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field, model_validator

from .brief import ContentBrief
from .segment import Segment, SegmentList


class ScriptTone(str, Enum):
    """Tone options for the script."""

    EMPATHETIC = "empathetic"
    PASSIONATE = "passionate"
    CALM = "calm"
    URGENT = "urgent"
    HOPEFUL = "hopeful"
    EDUCATIONAL = "educational"
    CONVERSATIONAL = "conversational"


class ScriptOption(BaseModel):
    """A single script option (for A/B testing)."""

    option_id: str = Field(
        description="Unique identifier (A, B, or C)",
        pattern="^[A-C]$"
    )
    title: str = Field(
        description="Short title for the script option",
        max_length=100
    )
    hook: str = Field(
        description="Opening hook in Hebrew",
        max_length=200
    )
    summary: str = Field(
        description="Brief summary of the script approach",
        max_length=300
    )
    tone: ScriptTone = Field(
        description="Overall tone of the script"
    )
    full_text: str = Field(
        description="Complete Hebrew script text",
        min_length=100,
        max_length=3000
    )
    estimated_duration: float = Field(
        description="Estimated total duration in seconds",
        ge=30.0,
        le=90.0
    )
    key_points: list[str] = Field(
        description="Main points covered in the script",
        min_length=2,
        max_length=5
    )

    class Config:
        use_enum_values = True


class ScriptOptions(BaseModel):
    """Three script options for A/B testing."""

    options: list[ScriptOption] = Field(
        description="Three script options to choose from",
        min_length=3,
        max_length=3
    )

    def get_option(self, option_id: str) -> Optional[ScriptOption]:
        """Get option by ID."""
        for option in self.options:
            if option.option_id == option_id:
                return option
        return None


class ScriptSelection(BaseModel):
    """LLM's selection of the best script option."""

    selected_option: str = Field(
        description="Selected option ID (A, B, or C)",
        pattern="^[A-C]$"
    )
    reasoning: str = Field(
        description="Explanation for why this option was selected",
        max_length=500
    )
    improvements: Optional[list[str]] = Field(
        default=None,
        description="Optional suggested improvements",
        max_length=3
    )


class Script(BaseModel):
    """Complete script with segments."""

    topic: str = Field(
        description="Main topic of the video"
    )
    angle: str = Field(
        description="Specific angle or guidelines used"
    )
    selected_option: ScriptOption = Field(
        description="The selected script option"
    )
    segments: SegmentList = Field(
        description="Segmented script with scene directions"
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Creation timestamp"
    )
    selection_reasoning: Optional[str] = Field(
        default=None,
        description="Why this option was selected"
    )

    def total_estimated_duration(self) -> float:
        """Get total estimated duration."""
        return self.segments.total_estimated_duration()


class ScriptRequest(BaseModel):
    """Request to generate a script.

    Supports two modes:
    1. Simple: topic + angle (short strings)
    2. Detailed: ContentBrief (structured brief with key points, rhetorical devices, etc.)

    When a brief is provided, topic and angle are derived from it.
    """

    # Simple mode fields (can be derived from brief)
    topic: Optional[str] = Field(
        default=None,
        description="Topic for the video (e.g., 'government accountability')",
        max_length=200
    )
    angle: Optional[str] = Field(
        default=None,
        description="Angle/guidelines (e.g., 'empathetic, solution-focused')",
        max_length=300
    )

    # Detailed mode field
    brief: Optional[ContentBrief] = Field(
        default=None,
        description="Detailed content brief with key points and rhetorical direction"
    )

    # Common fields
    target_duration: float = Field(
        default=60.0,
        description="Target duration in seconds",
        ge=30.0,
        le=120.0
    )
    min_segments: int = Field(
        default=6,
        description="Minimum number of segments"
    )
    max_segments: int = Field(
        default=8,
        description="Maximum number of segments"
    )
    reference_image_path: Optional[str] = Field(
        default=None,
        description="Path to reference image for character"
    )

    @model_validator(mode="after")
    def validate_input_mode(self):
        """Ensure either topic/angle or brief is provided."""
        has_simple = self.topic is not None and self.angle is not None
        has_brief = self.brief is not None

        if not has_simple and not has_brief:
            raise ValueError("Must provide either (topic + angle) or brief")

        # If brief provided, derive topic/angle from it
        if has_brief and not has_simple:
            self.topic = self.brief.title
            self.angle = f"{self.brief.emotional_tone}, {', '.join(self.brief.rhetorical_devices)}"

        return self

    @classmethod
    def from_brief_file(cls, path: Path, **kwargs) -> "ScriptRequest":
        """Create request from a brief file (YAML or Markdown)."""
        if path.suffix in (".yaml", ".yml"):
            brief = ContentBrief.from_yaml(path)
        elif path.suffix == ".md":
            brief = ContentBrief.from_markdown(path)
        else:
            raise ValueError(f"Unsupported brief format: {path.suffix}")

        return cls(brief=brief, **kwargs)

    def get_prompt_context(self) -> str:
        """Get the full prompt context for the LLM.

        Returns detailed brief context if available, otherwise simple topic/angle.
        """
        if self.brief:
            return self.brief.to_prompt_context()
        return f"נושא: {self.topic}\nכיוון: {self.angle}"

    def has_detailed_brief(self) -> bool:
        """Check if using detailed brief mode."""
        return self.brief is not None
