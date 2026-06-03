"""Scene schema for image generation prompts."""

from typing import Optional

from pydantic import BaseModel, Field

from .segment import CameraAngle, Expression, Lighting


class CharacterDescription(BaseModel):
    """Description of the character for consistent image generation."""

    gender: str = Field(
        description="Character gender (male/female/neutral)",
        pattern="^(male|female|neutral)$"
    )
    age_range: str = Field(
        description="Age range (e.g., '30-40', '50-60')",
        pattern="^\\d{2}-\\d{2}$"
    )
    appearance: str = Field(
        description="Brief appearance description",
        max_length=200
    )
    clothing_style: str = Field(
        description="Typical clothing style",
        max_length=100
    )
    key_features: list[str] = Field(
        description="Distinctive features for consistency",
        max_length=5
    )


class ImagePrompt(BaseModel):
    """Prompt for generating a character image."""

    segment_index: int = Field(
        description="Index of the segment this image is for"
    )
    camera_angle: CameraAngle = Field(
        description="Camera angle for the shot"
    )
    lighting: Lighting = Field(
        description="Lighting setup"
    )
    expression: Expression = Field(
        description="Facial expression"
    )
    setting: str = Field(
        description="Background setting description",
        max_length=150
    )
    character_description: str = Field(
        description="Character appearance for this shot",
        max_length=200
    )
    full_prompt: str = Field(
        description="Complete image generation prompt",
        max_length=1000
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="What to avoid in the image",
        max_length=500
    )

    class Config:
        use_enum_values = True


class ImagePromptBatch(BaseModel):
    """Batch of image prompts for all segments."""

    character: CharacterDescription = Field(
        description="Base character description for consistency"
    )
    prompts: list[ImagePrompt] = Field(
        description="Image prompts for each segment",
        min_length=1
    )

    def get_prompt(self, segment_index: int) -> Optional[ImagePrompt]:
        """Get prompt by segment index."""
        for prompt in self.prompts:
            if prompt.segment_index == segment_index:
                return prompt
        return None


class MotionPrompt(BaseModel):
    """Motion prompt for video generation (Workflow 2)."""

    segment_index: int = Field(
        description="Index of the segment this motion is for"
    )
    motion_type: str = Field(
        description="Type of motion (e.g., 'subtle head movement', 'gesturing')",
        max_length=50
    )
    motion_description: str = Field(
        description="Detailed motion description",
        max_length=300
    )
    intensity: str = Field(
        description="Motion intensity (subtle, moderate, dynamic)",
        pattern="^(subtle|moderate|dynamic)$"
    )
    duration_hint: Optional[float] = Field(
        default=None,
        description="Suggested motion duration in seconds"
    )


class MotionPromptBatch(BaseModel):
    """Batch of motion prompts for all segments."""

    prompts: list[MotionPrompt] = Field(
        description="Motion prompts for each segment",
        min_length=1
    )

    def get_prompt(self, segment_index: int) -> Optional[MotionPrompt]:
        """Get motion prompt by segment index."""
        for prompt in self.prompts:
            if prompt.segment_index == segment_index:
                return prompt
        return None
