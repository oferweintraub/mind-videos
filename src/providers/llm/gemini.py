"""Gemini LLM provider with Instructor integration."""

import logging
from typing import Any, Optional, TypeVar

import google.generativeai as genai
import instructor

from ..base import (
    AuthenticationError,
    BaseLLMProvider,
    ContentError,
    ProviderError,
    RateLimitError,
    RetryConfig,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GeminiProvider(BaseLLMProvider):
    """Gemini LLM provider with structured output support via Instructor.

    Drop-in replacement for Claude provider with same interface.
    Supports Gemini 3 Flash and Pro models.
    """

    DEFAULT_MODEL = "gemini-3-flash-preview"
    MAX_TOKENS = 4096

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        max_tokens: int = MAX_TOKENS,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 60.0,
    ):
        super().__init__(
            name="gemini",
            api_key=api_key,
            retry_config=retry_config,
            timeout=timeout,
        )
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens

        # Configure the Google AI SDK
        genai.configure(api_key=api_key)

        # Create base Gemini model
        self._base_model = genai.GenerativeModel(self.model)

        # Create Instructor-wrapped client for structured outputs
        self._instructor_client = instructor.from_gemini(
            client=genai.GenerativeModel(self.model),
            mode=instructor.Mode.GEMINI_JSON,
        )

    async def health_check(self) -> bool:
        """Check if Gemini API is accessible."""
        try:
            # Make a minimal API call to verify connectivity
            response = self._base_model.generate_content("Hi")
            return response is not None
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return False

    def _handle_api_error(self, error: Exception) -> None:
        """Convert Google AI errors to provider errors."""
        error_str = str(error).lower()

        if "api key" in error_str or "invalid" in error_str or "401" in error_str:
            raise AuthenticationError(
                "Invalid Google API key",
                self.name,
            )

        if "429" in error_str or "rate" in error_str or "quota" in error_str:
            raise RateLimitError(
                "Gemini rate limit exceeded",
                self.name,
                retry_after=60.0,
            )

        if "safety" in error_str or "blocked" in error_str:
            raise ContentError(
                f"Content blocked by Gemini safety filters: {error}",
                self.name,
            )

        raise ProviderError(str(error), self.name)

    def _build_prompt_with_system(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Build combined prompt with system instructions.

        Gemini handles system prompts differently than Claude,
        so we prepend them to the user prompt.
        """
        if system_prompt:
            return f"""System Instructions:
{system_prompt}

User Request:
{prompt}"""
        return prompt

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_model: Optional[type[T]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """Generate a response from Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            response_model: Optional Pydantic model for structured output
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated text or structured response if response_model is provided
        """
        max_tokens = max_tokens or self.max_tokens

        # Build combined prompt
        full_prompt = self._build_prompt_with_system(prompt, system_prompt)

        # Configure generation
        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        try:
            if response_model is not None:
                # Use Instructor for structured output
                response = self._instructor_client.messages.create(
                    messages=[{"role": "user", "content": full_prompt}],
                    response_model=response_model,
                    generation_config=generation_config,
                    **kwargs,
                )
                return response

            else:
                # Regular text generation
                response = self._base_model.generate_content(
                    full_prompt,
                    generation_config=generation_config,
                    **kwargs,
                )

                # Extract text from response
                if response.text:
                    return response.text
                return ""

        except Exception as e:
            self._handle_api_error(e)

    async def generate_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_model: Optional[type[T]] = None,
        **kwargs,
    ) -> Any:
        """Generate with automatic retry on failure.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            response_model: Optional Pydantic model for structured output
            **kwargs: Additional parameters

        Returns:
            Generated response
        """
        async def _generate():
            return await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                response_model=response_model,
                **kwargs,
            )

        result = await self._retry_operation(_generate, "generate")

        if not result.success:
            raise result.error or ProviderError("Generation failed", self.name)

        return result.data

    async def generate_script_options(
        self,
        topic: str,
        angle: str,
        target_duration: float = 60.0,
        prompt_context: Optional[str] = None,
    ) -> Any:
        """Generate script options for A/B testing.

        Args:
            topic: Topic for the video
            angle: Angle/guidelines for the script
            target_duration: Target duration in seconds
            prompt_context: Optional detailed prompt context from ContentBrief

        Returns:
            ScriptOptions object with 3 options
        """
        from ...schemas import ScriptOptions

        system_prompt = """You are an expert Hebrew scriptwriter specializing in
educational content about democracy, accountability, empathy, and diverse perspectives.

Your scripts should:
- Be written entirely in Hebrew
- Be engaging and educational
- Promote understanding and empathy
- Be appropriate for general audiences
- Target the specified duration

Generate 3 distinct script options (A, B, C) with different approaches to the topic."""

        # Use detailed brief context if provided
        if prompt_context:
            prompt = f"""Create 3 script options for a Hebrew educational video based on the following detailed brief.

{prompt_context}

Target Duration: {target_duration} seconds

IMPORTANT INSTRUCTIONS:
- Follow the key points in the order given - they are your roadmap
- Use the specified emotional tone throughout
- Incorporate the rhetorical devices listed
- Include the must-have phrases where natural
- Weave in the rhetorical questions
- End with the call to action

Each option should:
- Cover ALL key points in the brief
- Use a slightly different narrative approach
- Have a compelling hook that draws viewers in
- Match the specified emotional tone

Please generate exactly 3 options labeled A, B, and C."""
        else:
            # Simple mode - topic and angle only
            prompt = f"""Create 3 script options for a Hebrew educational video.

Topic: {topic}
Angle/Guidelines: {angle}
Target Duration: {target_duration} seconds

Each option should have:
- A unique approach/angle
- A compelling hook
- Clear key points
- Appropriate tone for the guidelines

Please generate exactly 3 options labeled A, B, and C."""

        return await self.generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            response_model=ScriptOptions,
            temperature=0.8,
        )

    async def select_best_script(
        self,
        options: Any,
        selection_criteria: Optional[str] = None,
    ) -> Any:
        """Select the best script option (LLM-as-judge).

        Args:
            options: ScriptOptions object with 3 options
            selection_criteria: Optional criteria for selection

        Returns:
            ScriptSelection with chosen option and reasoning
        """
        from ...schemas import ScriptSelection

        system_prompt = """You are an expert content evaluator specializing in
educational video content. Evaluate script options based on:
- Engagement potential
- Educational value
- Emotional resonance
- Clarity of message
- Target audience appropriateness"""

        criteria = selection_criteria or "best overall impact and engagement"

        options_text = "\n\n".join([
            f"Option {opt.option_id}:\nTitle: {opt.title}\nHook: {opt.hook}\n"
            f"Tone: {opt.tone}\nSummary: {opt.summary}\n"
            f"Key Points: {', '.join(opt.key_points)}"
            for opt in options.options
        ])

        prompt = f"""Evaluate these 3 script options and select the best one.

Selection Criteria: {criteria}

{options_text}

Select the best option (A, B, or C) and explain your reasoning."""

        return await self.generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            response_model=ScriptSelection,
            temperature=0.3,
        )

    async def segment_script(
        self,
        script_text: str,
        min_segments: int = 6,
        max_segments: int = 8,
        target_segment_duration: float = 8.0,
    ) -> Any:
        """Break a script into segments with scene directions.

        Args:
            script_text: Full script text in Hebrew
            min_segments: Minimum number of segments
            max_segments: Maximum number of segments
            target_segment_duration: Target duration per segment in seconds

        Returns:
            SegmentList with segments and scene directions
        """
        from ...schemas import SegmentList

        system_prompt = """You are an expert video director specializing in
talking-head educational videos. Break scripts into segments with appropriate
scene directions for each segment.

For each segment, specify:
- Camera angle (close_up, medium, wide, etc.)
- Lighting (natural, soft, dramatic, etc.)
- Expression (neutral, thoughtful, concerned, hopeful, etc.)
- Setting description
- Purpose of the segment"""

        prompt = f"""Break this Hebrew script into {min_segments}-{max_segments} segments.

Target segment duration: {target_segment_duration} seconds each

Script:
{script_text}

For each segment:
1. Extract the text portion
2. Estimate duration (based on Hebrew speech pace ~15 chars/sec)
3. Assign appropriate scene direction
4. Describe the segment's purpose

Ensure variety in camera angles and expressions across segments."""

        return await self.generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            response_model=SegmentList,
            temperature=0.5,
        )
