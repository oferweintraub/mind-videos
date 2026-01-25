"""Brief schema for detailed video content direction."""

from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class EmotionalTone(str, Enum):
    """Primary emotional tone for the video."""

    ANGRY = "angry"
    HOPEFUL = "hopeful"
    CYNICAL = "cynical"
    EMPATHETIC = "empathetic"
    URGENT = "urgent"
    CONTEMPLATIVE = "contemplative"
    SATIRICAL = "satirical"
    DETERMINED = "determined"
    SORROWFUL = "sorrowful"
    DEFIANT = "defiant"


class RhetoricalDevice(str, Enum):
    """Rhetorical devices to use."""

    METAPHORS = "metaphors"
    RHETORICAL_QUESTIONS = "rhetorical_questions"
    REPETITION = "repetition"
    CONTRAST = "contrast"
    PERSONAL_STORIES = "personal_stories"
    STATISTICS = "statistics"
    ANALOGIES = "analogies"
    IRONY = "irony"
    CALL_TO_ACTION = "call_to_action"
    DIRECT_ADDRESS = "direct_address"


class ContentBrief(BaseModel):
    """Detailed brief for video content generation.

    This replaces the simple topic/angle approach with a structured
    brief that provides the LLM with clear direction on:
    - What arguments to make
    - What rhetorical devices to use
    - What emotional tone to strike
    - What call to action to include
    """

    # Core identity
    title: str = Field(
        description="Short title/headline for the video (Hebrew)",
        max_length=100
    )

    subtitle: Optional[str] = Field(
        default=None,
        description="Optional subtitle or tagline",
        max_length=200
    )

    # Content direction - THE HEART OF THE BRIEF
    key_points: list[str] = Field(
        description="Numbered list of key arguments/points to make (in order of importance)",
        min_length=2,
        max_length=10
    )

    rhetorical_questions: Optional[list[str]] = Field(
        default=None,
        description="Powerful questions to pose to the audience",
        max_length=5
    )

    must_include_phrases: Optional[list[str]] = Field(
        default=None,
        description="Specific Hebrew phrases that MUST appear in the script",
        max_length=5
    )

    call_to_action: Optional[str] = Field(
        default=None,
        description="What should the viewer do/think/feel after watching?",
        max_length=300
    )

    supporting_facts: Optional[list[str]] = Field(
        default=None,
        description="Facts, statistics, or examples to reference",
        max_length=5
    )

    # Style direction
    emotional_tone: EmotionalTone = Field(
        description="Primary emotional tone"
    )

    secondary_tones: Optional[list[EmotionalTone]] = Field(
        default=None,
        description="Secondary emotional tones to weave in",
        max_length=2
    )

    rhetorical_devices: list[RhetoricalDevice] = Field(
        description="Rhetorical devices to employ",
        min_length=1,
        max_length=4
    )

    # Audience and context
    target_audience: Optional[str] = Field(
        default="Israeli general public",
        description="Who is this video for?",
        max_length=200
    )

    context: Optional[str] = Field(
        default=None,
        description="Background context the LLM should know",
        max_length=500
    )

    # Constraints
    avoid: Optional[list[str]] = Field(
        default=None,
        description="Topics, phrases, or approaches to explicitly avoid",
        max_length=5
    )

    # Narrative structure hints
    opening_hook: Optional[str] = Field(
        default=None,
        description="Suggested opening hook or first line",
        max_length=200
    )

    closing_statement: Optional[str] = Field(
        default=None,
        description="Suggested closing statement or last line",
        max_length=200
    )

    class Config:
        use_enum_values = True

    @classmethod
    def from_yaml(cls, path: Path) -> "ContentBrief":
        """Load brief from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def from_markdown(cls, path: Path) -> "ContentBrief":
        """Load brief from Markdown file with YAML frontmatter."""
        content = path.read_text(encoding="utf-8")

        # Parse YAML frontmatter (between --- markers)
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                body = parts[2].strip()

                # If key_points not in frontmatter, parse from body
                if "key_points" not in frontmatter and body:
                    lines = [
                        line.strip().lstrip("0123456789.-) ").strip()
                        for line in body.split("\n")
                        if line.strip() and not line.startswith("#")
                    ]
                    frontmatter["key_points"] = [l for l in lines if l]

                return cls(**frontmatter)

        raise ValueError(f"Invalid brief format in {path}")

    def to_yaml(self, path: Path) -> None:
        """Save brief to YAML file."""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                self.model_dump(exclude_none=True),
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

    def to_prompt_context(self) -> str:
        """Convert brief to detailed prompt context for LLM."""
        sections = []

        # Title
        sections.append(f"# כותרת: {self.title}")
        if self.subtitle:
            sections.append(f"תת-כותרת: {self.subtitle}")

        # Key points - THE MOST IMPORTANT PART
        sections.append("\n## נקודות מפתח (לפי סדר חשיבות):")
        for i, point in enumerate(self.key_points, 1):
            sections.append(f"{i}. {point}")

        # Rhetorical questions
        if self.rhetorical_questions:
            sections.append("\n## שאלות רטוריות לשלב:")
            for q in self.rhetorical_questions:
                sections.append(f"- {q}")

        # Must-include phrases
        if self.must_include_phrases:
            sections.append("\n## ביטויים שחייבים להופיע:")
            for phrase in self.must_include_phrases:
                sections.append(f"- \"{phrase}\"")

        # Supporting facts
        if self.supporting_facts:
            sections.append("\n## עובדות תומכות:")
            for fact in self.supporting_facts:
                sections.append(f"- {fact}")

        # Call to action
        if self.call_to_action:
            sections.append(f"\n## קריאה לפעולה:\n{self.call_to_action}")

        # Style direction
        sections.append(f"\n## טון רגשי: {self.emotional_tone}")
        if self.secondary_tones:
            sections.append(f"טונים משניים: {', '.join(self.secondary_tones)}")

        sections.append(f"\n## כלים רטוריים לשימוש: {', '.join(self.rhetorical_devices)}")

        # Context
        if self.context:
            sections.append(f"\n## הקשר רקע:\n{self.context}")

        # Audience
        if self.target_audience:
            sections.append(f"\n## קהל יעד: {self.target_audience}")

        # Constraints
        if self.avoid:
            sections.append("\n## להימנע מ:")
            for item in self.avoid:
                sections.append(f"- {item}")

        # Narrative hints
        if self.opening_hook:
            sections.append(f"\n## הצעה לפתיחה:\n\"{self.opening_hook}\"")

        if self.closing_statement:
            sections.append(f"\n## הצעה לסיום:\n\"{self.closing_statement}\"")

        return "\n".join(sections)


# Convenience function to create a brief from simple inputs
def create_brief(
    title: str,
    key_points: list[str],
    emotional_tone: str = "determined",
    rhetorical_devices: Optional[list[str]] = None,
    **kwargs,
) -> ContentBrief:
    """Create a ContentBrief from simple inputs.

    Args:
        title: Video title
        key_points: List of key arguments/points
        emotional_tone: Primary emotional tone
        rhetorical_devices: List of rhetorical devices to use
        **kwargs: Additional brief fields

    Returns:
        ContentBrief instance
    """
    devices = rhetorical_devices or ["rhetorical_questions", "contrast"]

    return ContentBrief(
        title=title,
        key_points=key_points,
        emotional_tone=EmotionalTone(emotional_tone),
        rhetorical_devices=[RhetoricalDevice(d) for d in devices],
        **kwargs,
    )
