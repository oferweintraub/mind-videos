"""Scene planner service for image generation prompts."""

import logging
from typing import Optional, Union

from ..config import Config, get_config
from ..providers.llm.claude import ClaudeProvider
from ..providers.llm.gemini import GeminiProvider
from ..schemas import (
    CharacterDescription,
    ImagePrompt,
    ImagePromptBatch,
    MotionPrompt,
    MotionPromptBatch,
    Segment,
    SegmentList,
)

logger = logging.getLogger(__name__)


class ScenePlanner:
    """Service for planning scenes and generating image prompts.

    Handles:
    - Creating character descriptions for consistency
    - Generating image prompts for each segment
    - Creating motion prompts for Workflow 2
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

    async def create_character_description(
        self,
        reference_description: Optional[str] = None,
    ) -> CharacterDescription:
        """Create a character description for consistent image generation.

        Args:
            reference_description: Optional description from reference image

        Returns:
            CharacterDescription for image generation
        """
        llm = self._get_llm_provider()

        system_prompt = """You are a character designer for educational videos.
Create a consistent character description that can be used to generate
multiple images with the same appearance.

The character should:
- Look professional and trustworthy
- Be suitable for educational content
- Have clear, distinctive features for consistency"""

        prompt = f"""Create a character description for a Hebrew educational video presenter.

{f'Reference: {reference_description}' if reference_description else 'Create a generic professional presenter.'}

The character should be:
- Professional appearance
- Approachable and trustworthy
- Suitable for discussing democracy, accountability, and empathy

Provide specific details for consistent image generation."""

        character = await llm.generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            response_model=CharacterDescription,
            temperature=0.6,
        )

        logger.info(f"Created character: {character.gender}, {character.age_range}")

        return character

    def _build_image_prompt(
        self,
        segment: Segment,
        character: CharacterDescription,
    ) -> str:
        """Build a complete image generation prompt.

        Args:
            segment: Segment with scene definition
            character: Character description for consistency

        Returns:
            Complete prompt string for image generation
        """
        scene = segment.scene

        # Build character description
        char_desc = (
            f"{character.gender}, {character.age_range} years old, "
            f"{character.appearance}, wearing {character.clothing_style}"
        )

        # Add key features
        features = ", ".join(character.key_features)

        # Build scene description
        scene_desc = (
            f"{scene.camera_angle.replace('_', ' ')} shot, "
            f"{scene.lighting} lighting, "
            f"{scene.expression} expression, "
            f"{scene.setting}"
        )

        # Combine into full prompt
        prompt = (
            f"Professional photograph of {char_desc}. "
            f"Key features: {features}. "
            f"{scene_desc}. "
            f"High quality, professional lighting, 4K resolution. "
            f"Suitable for educational video thumbnail."
        )

        return prompt

    def _build_negative_prompt(self) -> str:
        """Build negative prompt for image generation."""
        return (
            "blurry, low quality, distorted, deformed, ugly, "
            "unprofessional, inappropriate, cartoon, anime, "
            "multiple people, text, watermark, logo"
        )

    async def generate_image_prompts(
        self,
        segments: SegmentList,
        character: Optional[CharacterDescription] = None,
    ) -> ImagePromptBatch:
        """Generate image prompts for all segments.

        Args:
            segments: SegmentList with scene definitions
            character: Optional character description (created if not provided)

        Returns:
            ImagePromptBatch with prompts for each segment
        """
        # Create character if not provided
        if character is None:
            character = await self.create_character_description()

        prompts = []

        for segment in segments.segments:
            # Build the full prompt
            full_prompt = self._build_image_prompt(segment, character)

            prompt = ImagePrompt(
                segment_index=segment.index,
                camera_angle=segment.scene.camera_angle,
                lighting=segment.scene.lighting,
                expression=segment.scene.expression,
                setting=segment.scene.setting,
                character_description=(
                    f"{character.gender}, {character.age_range}, "
                    f"{character.appearance}"
                ),
                full_prompt=full_prompt,
                negative_prompt=self._build_negative_prompt(),
            )

            prompts.append(prompt)

        logger.info(f"Generated {len(prompts)} image prompts")

        return ImagePromptBatch(
            character=character,
            prompts=prompts,
        )

    async def generate_motion_prompts(
        self,
        segments: SegmentList,
    ) -> MotionPromptBatch:
        """Generate motion prompts for Workflow 2.

        Args:
            segments: SegmentList with scene definitions

        Returns:
            MotionPromptBatch with motion descriptions for each segment
        """
        llm = self._get_llm_provider()

        system_prompt = """You are a video director specializing in talking-head videos.
Create subtle, natural motion descriptions for video generation.

Motion should:
- Be subtle and professional
- Match the emotional content of the text
- Avoid distracting movements
- Be suitable for lip-sync overlay"""

        prompts = []

        for segment in segments.segments:
            prompt = f"""Create a motion description for this video segment.

Text: {segment.text[:200]}...
Expression: {segment.scene.expression}
Camera: {segment.scene.camera_angle}
Duration: {segment.duration_estimate} seconds

Describe subtle, natural movements suitable for this segment."""

            motion = await llm.generate_with_retry(
                prompt=prompt,
                system_prompt=system_prompt,
                response_model=MotionPrompt,
                temperature=0.5,
            )

            motion.segment_index = segment.index
            prompts.append(motion)

        logger.info(f"Generated {len(prompts)} motion prompts")

        return MotionPromptBatch(prompts=prompts)

    async def ensure_scene_variety(
        self,
        segments: SegmentList,
    ) -> SegmentList:
        """Ensure variety in scene directions across segments.

        Args:
            segments: Original SegmentList

        Returns:
            SegmentList with improved variety
        """
        # Check for consecutive identical camera angles
        from ..schemas.segment import CameraAngle, Expression

        camera_angles = [s.scene.camera_angle for s in segments.segments]
        expressions = [s.scene.expression for s in segments.segments]

        # Count consecutive duplicates
        consecutive_cameras = sum(
            1 for i in range(1, len(camera_angles))
            if camera_angles[i] == camera_angles[i-1]
        )

        consecutive_expressions = sum(
            1 for i in range(1, len(expressions))
            if expressions[i] == expressions[i-1]
        )

        # If too many consecutive duplicates, regenerate
        if consecutive_cameras > 2 or consecutive_expressions > 2:
            logger.info("Improving scene variety...")

            llm = self._get_llm_provider()

            system_prompt = """You are a video director. Improve the variety
of scene directions for a talking-head video. Avoid consecutive identical
camera angles or expressions. Ensure smooth transitions."""

            segments_desc = "\n".join([
                f"Segment {s.index}: {s.scene.camera_angle}, {s.scene.expression}, {s.purpose[:50]}"
                for s in segments.segments
            ])

            prompt = f"""Improve the variety of these scene directions.

Current segments:
{segments_desc}

Update camera angles and expressions to:
1. Avoid consecutive identical values
2. Create visual variety
3. Match the emotional content
4. Maintain professional look"""

            improved = await llm.generate_with_retry(
                prompt=prompt,
                system_prompt=system_prompt,
                response_model=SegmentList,
                temperature=0.6,
            )

            # Preserve original text and paths
            for i, seg in enumerate(improved.segments):
                if i < len(segments.segments):
                    seg.text = segments.segments[i].text
                    seg.audio_path = segments.segments[i].audio_path
                    seg.video_path = segments.segments[i].video_path

            logger.info("Scene variety improved")
            return improved

        return segments
