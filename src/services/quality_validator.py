"""Quality validator service for video segment validation."""

import logging
from pathlib import Path
from typing import Optional, Union

from ..config import Config, get_config
from ..providers.llm.claude import ClaudeProvider
from ..providers.llm.gemini import GeminiProvider
from ..schemas import (
    ContentValidation,
    ImageValidation,
    QualityScore,
    Segment,
    SegmentList,
    SegmentValidation,
    ValidationDecision,
    VideoValidation,
)

logger = logging.getLogger(__name__)


class QualityValidator:
    """Service for validating video segment quality.

    Handles:
    - Video segment quality scoring
    - Image quality validation
    - Content appropriateness checks
    - Remake decisions
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        llm_provider: Optional[Union[ClaudeProvider, GeminiProvider]] = None,
    ):
        self.config = config or get_config()
        self._llm_provider = llm_provider

    def _get_llm_provider(self) -> Union[ClaudeProvider, GeminiProvider]:
        """Get or create LLM provider based on config."""
        if self._llm_provider is not None:
            return self._llm_provider

        if self.config.llm.provider == "gemini":
            self._llm_provider = GeminiProvider(
                api_key=self.config.api_keys.google,
                model=self.config.llm.gemini_model,
            )
        else:
            self._llm_provider = ClaudeProvider(
                api_key=self.config.api_keys.anthropic,
                model=self.config.llm.claude_model,
            )

        return self._llm_provider

    def _score_to_numeric(self, score: QualityScore) -> float:
        """Convert quality score to numeric value."""
        scores = {
            QualityScore.EXCELLENT: 1.0,
            QualityScore.GOOD: 0.8,
            QualityScore.ACCEPTABLE: 0.6,
            QualityScore.POOR: 0.4,
            QualityScore.UNACCEPTABLE: 0.2,
        }
        return scores.get(score, 0.5)

    async def validate_segment(
        self,
        segment: Segment,
        video_path: Optional[Path] = None,
        image_path: Optional[Path] = None,
    ) -> SegmentValidation:
        """Validate a single video segment.

        Args:
            segment: Segment to validate
            video_path: Path to generated video (optional for analysis)
            image_path: Path to generated image (optional for analysis)

        Returns:
            SegmentValidation with scores and decision
        """
        llm = self._get_llm_provider()

        # Build validation prompt
        system_prompt = """You are a video quality assurance specialist.
Evaluate video segments for:
- Lip sync quality (if audio present)
- Face visibility and clarity
- Visual consistency with intended scene
- Audio quality
- Overall professional appearance

Be strict but fair in your evaluation."""

        prompt = f"""Evaluate this video segment:

Segment {segment.index}:
- Text: {segment.text[:200]}...
- Duration: {segment.duration_estimate}s
- Scene: {segment.scene.camera_angle}, {segment.scene.expression}, {segment.scene.setting}
- Purpose: {segment.purpose}
{f'- Video path: {video_path}' if video_path else ''}
{f'- Image path: {image_path}' if image_path else ''}

Evaluate quality scores for lip_sync, face_visibility, visual_consistency,
audio_quality, and overall_quality.

Provide a decision: approve (quality >= threshold), remake (quality issues),
or manual_review (uncertain).

Threshold: {self.config.pipeline.quality_threshold}"""

        validation = await llm.generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            response_model=SegmentValidation,
            temperature=0.3,
        )

        # Override segment_index to match
        validation.segment_index = segment.index

        # Calculate numeric score
        scores = [
            self._score_to_numeric(validation.lip_sync_quality),
            self._score_to_numeric(validation.face_visibility),
            self._score_to_numeric(validation.visual_consistency),
            self._score_to_numeric(validation.audio_quality),
            self._score_to_numeric(validation.overall_quality),
        ]
        validation.quality_score = sum(scores) / len(scores)

        # Determine decision based on threshold
        threshold = self.config.pipeline.quality_threshold
        if validation.quality_score >= threshold:
            validation.decision = ValidationDecision.APPROVE
        elif validation.quality_score >= threshold * 0.7:
            validation.decision = ValidationDecision.MANUAL_REVIEW
        else:
            validation.decision = ValidationDecision.REMAKE

        logger.info(
            f"Segment {segment.index} validation: "
            f"score={validation.quality_score:.2f}, decision={validation.decision}"
        )

        return validation

    async def validate_video(
        self,
        segments: SegmentList,
    ) -> VideoValidation:
        """Validate all segments of a video.

        Args:
            segments: SegmentList with all segments

        Returns:
            VideoValidation with overall assessment
        """
        segment_validations = []

        for segment in segments.segments:
            video_path = Path(segment.video_path) if segment.video_path else None
            image_path = Path(segment.image_path) if segment.image_path else None

            validation = await self.validate_segment(
                segment=segment,
                video_path=video_path,
                image_path=image_path,
            )
            segment_validations.append(validation)

        # Calculate overall metrics
        scores = [v.quality_score for v in segment_validations]
        overall_score = sum(scores) / len(scores) if scores else 0.0

        approved = sum(1 for v in segment_validations if v.decision == ValidationDecision.APPROVE)
        remake = sum(1 for v in segment_validations if v.decision == ValidationDecision.REMAKE)
        review = sum(1 for v in segment_validations if v.decision == ValidationDecision.MANUAL_REVIEW)

        # Determine overall decision
        threshold = self.config.pipeline.quality_threshold
        if overall_score >= threshold and remake == 0:
            overall_decision = ValidationDecision.APPROVE
        elif remake > len(segments.segments) // 2:
            overall_decision = ValidationDecision.REMAKE
        else:
            overall_decision = ValidationDecision.MANUAL_REVIEW

        video_validation = VideoValidation(
            segment_validations=segment_validations,
            overall_quality_score=overall_score,
            segments_approved=approved,
            segments_needing_remake=remake,
            segments_needing_review=review,
            overall_decision=overall_decision,
            final_notes=f"Validated {len(segments.segments)} segments. "
                        f"Average quality: {overall_score:.2f}",
        )

        logger.info(
            f"Video validation complete: score={overall_score:.2f}, "
            f"approved={approved}, remake={remake}, review={review}"
        )

        return video_validation

    async def validate_content(
        self,
        text: str,
        topic: str,
        angle: str,
    ) -> ContentValidation:
        """Validate script content for appropriateness.

        Args:
            text: Script text to validate
            topic: Video topic
            angle: Video angle/guidelines

        Returns:
            ContentValidation with approval status
        """
        llm = self._get_llm_provider()

        system_prompt = """You are a content moderator for educational videos
about democracy, accountability, empathy, and diverse perspectives.

Evaluate content for:
- Appropriateness for general audiences
- Alignment with democratic values
- Factual accuracy concerns
- Tone matching the intended angle

Be thoughtful and fair in your evaluation."""

        prompt = f"""Evaluate this Hebrew script content:

Topic: {topic}
Angle: {angle}

Script:
{text}

Check:
1. Is the content appropriate for educational purposes?
2. Does it align with guidelines about democracy and empathy?
3. Is the tone appropriate for the stated angle?
4. Are there any factual concerns?

Provide your evaluation."""

        validation = await llm.generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            response_model=ContentValidation,
            temperature=0.3,
        )

        logger.info(f"Content validation: approval={validation.approval}")

        return validation

    async def validate_image(
        self,
        segment: Segment,
        image_bytes: Optional[bytes] = None,
        image_path: Optional[Path] = None,
    ) -> ImageValidation:
        """Validate a generated image for a segment.

        Args:
            segment: Segment the image is for
            image_bytes: Image data (optional)
            image_path: Path to image (optional)

        Returns:
            ImageValidation with scores and decision
        """
        llm = self._get_llm_provider()

        system_prompt = """You are an image quality specialist for educational videos.
Evaluate generated images for:
- Character consistency
- Expression accuracy
- Setting appropriateness
- Overall quality

Be strict but fair."""

        prompt = f"""Evaluate this image for segment {segment.index}:

Expected:
- Camera: {segment.scene.camera_angle}
- Expression: {segment.scene.expression}
- Setting: {segment.scene.setting}
- Lighting: {segment.scene.lighting}

{f'Image path: {image_path}' if image_path else 'Image provided inline'}

Evaluate:
1. Does the character match the expected description?
2. Is the expression correct?
3. Does the setting match?
4. What is the overall quality score (0-1)?

Provide your evaluation."""

        validation = await llm.generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            response_model=ImageValidation,
            temperature=0.3,
        )

        # Override segment_index
        validation.segment_index = segment.index

        # Determine decision
        threshold = self.config.pipeline.quality_threshold
        if validation.quality_score >= threshold:
            validation.decision = ValidationDecision.APPROVE
        elif validation.quality_score >= threshold * 0.7:
            validation.decision = ValidationDecision.MANUAL_REVIEW
        else:
            validation.decision = ValidationDecision.REMAKE

        logger.info(
            f"Image validation for segment {segment.index}: "
            f"score={validation.quality_score:.2f}, decision={validation.decision}"
        )

        return validation
