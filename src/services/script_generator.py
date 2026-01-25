"""Script generator service for creating video scripts."""

import logging
from typing import Optional, Union

from ..config import Config, get_config
from ..providers.llm.claude import ClaudeProvider
from ..providers.llm.gemini import GeminiProvider
from ..schemas import (
    Script,
    ScriptOption,
    ScriptOptions,
    ScriptRequest,
    ScriptSelection,
    SegmentList,
)

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """Service for generating and managing video scripts.

    Handles:
    - Generating 3 script options for A/B testing
    - LLM-as-judge selection of best script
    - Segmenting scripts into video segments
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
            # Default to Claude
            self._llm_provider = ClaudeProvider(
                api_key=self.config.api_keys.anthropic,
                model=self.config.llm.claude_model,
            )

        return self._llm_provider

    async def generate_options(
        self,
        request: ScriptRequest,
    ) -> ScriptOptions:
        """Generate 3 script options for A/B testing.

        Args:
            request: ScriptRequest with topic, angle, and parameters

        Returns:
            ScriptOptions with 3 distinct options
        """
        llm = self._get_llm_provider()

        logger.info(f"Generating script options for topic: {request.topic}")

        # Use detailed prompt context if brief is available
        prompt_context = request.get_prompt_context() if request.has_detailed_brief() else None

        options = await llm.generate_script_options(
            topic=request.topic,
            angle=request.angle,
            target_duration=request.target_duration,
            prompt_context=prompt_context,
        )

        logger.info(f"Generated {len(options.options)} script options")

        return options

    async def select_best_option(
        self,
        options: ScriptOptions,
        criteria: Optional[str] = None,
    ) -> ScriptSelection:
        """Use LLM-as-judge to select the best script option.

        Args:
            options: ScriptOptions with 3 options
            criteria: Optional custom selection criteria

        Returns:
            ScriptSelection with chosen option and reasoning
        """
        llm = self._get_llm_provider()

        logger.info("Selecting best script option...")

        selection = await llm.select_best_script(
            options=options,
            selection_criteria=criteria,
        )

        logger.info(f"Selected option {selection.selected_option}: {selection.reasoning[:100]}...")

        return selection

    async def segment_script(
        self,
        script: ScriptOption,
        min_segments: Optional[int] = None,
        max_segments: Optional[int] = None,
    ) -> SegmentList:
        """Break a script into segments with scene directions.

        Args:
            script: Selected ScriptOption
            min_segments: Minimum segments (from config if not specified)
            max_segments: Maximum segments (from config if not specified)

        Returns:
            SegmentList with segments and scene directions
        """
        llm = self._get_llm_provider()

        min_segs = min_segments or self.config.pipeline.segments_min
        max_segs = max_segments or self.config.pipeline.segments_max
        target_duration = (
            self.config.pipeline.segment_duration_min +
            self.config.pipeline.segment_duration_max
        ) / 2

        logger.info(f"Segmenting script into {min_segs}-{max_segs} segments...")

        segments = await llm.segment_script(
            script_text=script.full_text,
            min_segments=min_segs,
            max_segments=max_segs,
            target_segment_duration=target_duration,
        )

        logger.info(f"Created {len(segments.segments)} segments")

        return segments

    async def generate_script(
        self,
        request: ScriptRequest,
        auto_select: bool = True,
        selection_criteria: Optional[str] = None,
    ) -> Script:
        """Generate a complete script with segments.

        Args:
            request: ScriptRequest with topic and parameters
            auto_select: Whether to auto-select best option (vs returning all)
            selection_criteria: Optional criteria for selection

        Returns:
            Complete Script with segments
        """
        # Generate options
        options = await self.generate_options(request)

        # Select best option
        if auto_select:
            selection = await self.select_best_option(
                options=options,
                criteria=selection_criteria,
            )
            selected_option = options.get_option(selection.selected_option)
            selection_reasoning = selection.reasoning
        else:
            # Default to first option if not auto-selecting
            selected_option = options.options[0]
            selection_reasoning = "Manual selection required"

        if selected_option is None:
            raise ValueError(f"Could not find selected option")

        # Segment the script
        segments = await self.segment_script(selected_option)

        # Build complete Script
        script = Script(
            topic=request.topic,
            angle=request.angle,
            selected_option=selected_option,
            segments=segments,
            selection_reasoning=selection_reasoning,
        )

        logger.info(
            f"Generated complete script: {len(segments.segments)} segments, "
            f"~{segments.total_estimated_duration():.1f}s"
        )

        return script

    async def regenerate_segment(
        self,
        script: Script,
        segment_index: int,
    ) -> Script:
        """Regenerate a specific segment.

        Args:
            script: Original Script
            segment_index: Index of segment to regenerate

        Returns:
            Updated Script with new segment
        """
        llm = self._get_llm_provider()

        segment = script.segments.get_segment(segment_index)
        if segment is None:
            raise ValueError(f"Segment {segment_index} not found")

        # Generate new scene direction for this segment
        from ..schemas import SegmentList

        prompt = f"""Regenerate scene directions for this segment of a Hebrew educational video.

Segment text: {segment.text}
Duration estimate: {segment.duration_estimate} seconds
Previous purpose: {segment.purpose}

Provide new scene directions (camera angle, lighting, expression, setting) that:
- Differ from previous: camera={segment.scene.camera_angle}, expression={segment.scene.expression}
- Maintain variety with other segments
- Match the emotional tone of the text"""

        system_prompt = """You are a video director. Generate fresh scene directions
for a talking-head educational video segment. Ensure variety while maintaining
coherence with the overall video."""

        # Create a single-segment list for the response
        from ..schemas import Segment, SceneDefinition

        new_segment = await llm.generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            response_model=Segment,
            temperature=0.7,
        )

        # Update the segment in the script
        new_segment.index = segment_index
        new_segment.text = segment.text

        # Replace in segments list
        for i, seg in enumerate(script.segments.segments):
            if seg.index == segment_index:
                script.segments.segments[i] = new_segment
                break

        logger.info(f"Regenerated segment {segment_index}")

        return script
