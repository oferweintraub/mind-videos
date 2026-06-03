"""Validation schemas for quality checking."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class QualityScore(str, Enum):
    """Quality score levels."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNACCEPTABLE = "unacceptable"


class ValidationDecision(str, Enum):
    """Validation decision options."""

    APPROVE = "approve"
    REMAKE = "remake"
    MANUAL_REVIEW = "manual_review"


class SegmentValidation(BaseModel):
    """Validation result for a single segment."""

    segment_index: int = Field(
        description="Index of the validated segment"
    )

    # Quality scores
    lip_sync_quality: QualityScore = Field(
        description="Quality of lip synchronization"
    )
    face_visibility: QualityScore = Field(
        description="How well the face is visible"
    )
    visual_consistency: QualityScore = Field(
        description="Consistency with reference/other segments"
    )
    audio_quality: QualityScore = Field(
        description="Quality of the audio"
    )
    overall_quality: QualityScore = Field(
        description="Overall segment quality"
    )

    # Numeric score (0-1)
    quality_score: float = Field(
        description="Numeric quality score",
        ge=0.0,
        le=1.0
    )

    # Decision
    decision: ValidationDecision = Field(
        description="Validation decision"
    )
    issues: list[str] = Field(
        default_factory=list,
        description="List of identified issues",
        max_length=5
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Improvement suggestions",
        max_length=3
    )

    class Config:
        use_enum_values = True


class VideoValidation(BaseModel):
    """Validation result for the complete video."""

    segment_validations: list[SegmentValidation] = Field(
        description="Validation for each segment"
    )

    # Overall metrics
    overall_quality_score: float = Field(
        description="Average quality score across segments",
        ge=0.0,
        le=1.0
    )
    segments_approved: int = Field(
        description="Number of approved segments"
    )
    segments_needing_remake: int = Field(
        description="Number of segments needing remake"
    )
    segments_needing_review: int = Field(
        description="Number of segments needing manual review"
    )

    # Final decision
    overall_decision: ValidationDecision = Field(
        description="Overall validation decision"
    )
    final_notes: Optional[str] = Field(
        default=None,
        description="Final notes or recommendations",
        max_length=500
    )

    def get_segments_to_remake(self) -> list[int]:
        """Get indices of segments that need to be remade."""
        return [
            v.segment_index
            for v in self.segment_validations
            if v.decision == ValidationDecision.REMAKE
        ]

    def get_segments_for_review(self) -> list[int]:
        """Get indices of segments needing manual review."""
        return [
            v.segment_index
            for v in self.segment_validations
            if v.decision == ValidationDecision.MANUAL_REVIEW
        ]


class ContentValidation(BaseModel):
    """Validation for script content appropriateness."""

    is_appropriate: bool = Field(
        description="Whether content is appropriate"
    )
    aligns_with_guidelines: bool = Field(
        description="Whether content aligns with democracy/empathy guidelines"
    )
    tone_appropriate: bool = Field(
        description="Whether tone matches the requested angle"
    )
    factual_concerns: list[str] = Field(
        default_factory=list,
        description="Any factual accuracy concerns",
        max_length=3
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Suggestions for improvement",
        max_length=3
    )
    approval: bool = Field(
        description="Final content approval"
    )


class ImageValidation(BaseModel):
    """Validation for generated images."""

    segment_index: int = Field(
        description="Index of the segment this image is for"
    )
    matches_character: bool = Field(
        description="Whether image matches character description"
    )
    matches_expression: bool = Field(
        description="Whether expression matches segment requirement"
    )
    matches_setting: bool = Field(
        description="Whether setting matches segment requirement"
    )
    quality_score: float = Field(
        description="Image quality score",
        ge=0.0,
        le=1.0
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Identified issues",
        max_length=3
    )
    decision: ValidationDecision = Field(
        description="Validation decision"
    )

    class Config:
        use_enum_values = True
