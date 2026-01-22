"""Configuration management for Hebrew Democracy Video Pipeline."""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


# Load environment variables from .env file
load_dotenv()


class APIKeys(BaseModel):
    """API key configuration."""

    fal: str = Field(default="", description="Fal.ai API key (VEED, Kling, sync)")
    replicate: str = Field(default="", description="Replicate API token (fallback)")
    elevenlabs: str = Field(default="", description="ElevenLabs API key")
    anthropic: str = Field(default="", description="Anthropic API key (Claude)")
    google: str = Field(default="", description="Google API key (Gemini, Nano Banana)")

    @classmethod
    def from_env(cls) -> "APIKeys":
        """Load API keys from environment variables."""
        return cls(
            fal=os.getenv("FAL_API_KEY", ""),
            replicate=os.getenv("REPLICATE_API_TOKEN", ""),
            elevenlabs=os.getenv("ELEVENLABS_API_KEY", ""),
            anthropic=os.getenv("ANTHROPIC_API_KEY", ""),
            google=os.getenv("GOOGLE_API_KEY", ""),
        )


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = Field(default="claude", description="Primary LLM (claude or gemini)")
    claude_model: str = Field(default="claude-sonnet-4-5-20250929", description="Claude 4.5 Sonnet model ID")
    gemini_model: str = Field(default="gemini-3-flash-preview", description="Gemini 3 Flash model ID")
    max_retries: int = Field(default=3, description="Max retries on failure")
    timeout: int = Field(default=60, description="Timeout in seconds")


class AudioConfig(BaseModel):
    """Audio generation configuration."""

    provider: str = Field(default="elevenlabs", description="Audio provider")
    voice_id: str = Field(default="EXAVITQu4vr4xnSDxMaL", description="ElevenLabs voice ID")
    voice_name: str = Field(default="Jessica", description="Voice name for reference")
    model_id: str = Field(default="eleven_multilingual_v2", description="ElevenLabs model")
    stability: float = Field(default=0.5, description="Voice stability (0-1)")
    similarity_boost: float = Field(default=0.75, description="Voice similarity boost (0-1)")


class VideoConfig(BaseModel):
    """Video generation configuration."""

    primary_provider: str = Field(default="fal", description="Primary video provider")
    fallback_provider: str = Field(default="replicate", description="Fallback provider")
    resolution: str = Field(default="480p", description="Video resolution (480p or 720p)")
    max_retries: int = Field(default=3, description="Max retries per provider")
    poll_interval: int = Field(default=5, description="Polling interval in seconds")
    timeout: int = Field(default=300, description="Timeout in seconds")

    # VEED Fabric settings
    veed_model: str = Field(default="fal-ai/veed-video", description="VEED model ID on Fal.ai")
    veed_replicate_model: str = Field(
        default="veed/fabric-1.0",
        description="VEED model ID on Replicate"
    )

    # Kling settings
    kling_model: str = Field(default="fal-ai/kling-video/v2.5/pro", description="Kling model on Fal.ai")
    kling_replicate_model: str = Field(
        default="klingai/kling-2.5-pro",
        description="Kling model ID on Replicate"
    )

    # Sync Lipsync settings
    sync_model: str = Field(default="fal-ai/sync-lipsync-2-pro", description="Sync model on Fal.ai")
    sync_replicate_model: str = Field(
        default="sync/lipsync-2-pro",
        description="Sync model ID on Replicate"
    )


class ImageConfig(BaseModel):
    """Image generation configuration."""

    provider: str = Field(default="nano_banana", description="Image provider")
    model: str = Field(default="imagen-3.0-generate-002", description="Nano Banana model")
    aspect_ratio: str = Field(default="9:16", description="Image aspect ratio")
    number_of_images: int = Field(default=1, description="Images to generate per prompt")


class SubtitleConfig(BaseModel):
    """Subtitle configuration."""

    font: str = Field(default="Arial", description="Font name")
    font_size: int = Field(default=24, description="Font size")
    font_color: str = Field(default="white", description="Text color")
    background_color: str = Field(default="black@0.5", description="Background color with opacity")
    position: str = Field(default="bottom", description="Subtitle position")
    margin_v: int = Field(default=20, description="Vertical margin from edge")


class PipelineConfig(BaseModel):
    """Pipeline execution configuration."""

    default_workflow: int = Field(default=1, description="Default workflow (1 or 2)")
    segments_min: int = Field(default=6, description="Minimum segments per video")
    segments_max: int = Field(default=8, description="Maximum segments per video")
    segment_duration_min: float = Field(default=6.0, description="Min segment duration (seconds)")
    segment_duration_max: float = Field(default=10.0, description="Max segment duration (seconds)")
    preview_segments: int = Field(default=4, description="Segments for preview mode")
    quality_threshold: float = Field(default=0.7, description="Minimum quality score (0-1)")
    max_remake_attempts: int = Field(default=2, description="Max segment remake attempts")


class Config(BaseModel):
    """Main configuration container."""

    api_keys: APIKeys = Field(default_factory=APIKeys.from_env)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    image: ImageConfig = Field(default_factory=ImageConfig)
    subtitle: SubtitleConfig = Field(default_factory=SubtitleConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    # Paths
    output_dir: Path = Field(default=Path("output"), description="Output directory")
    config_dir: Path = Field(default=Path("config"), description="Config directory")

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from YAML file and environment."""
        config_data = {}

        if config_path is None:
            config_path = Path("config/default.yaml")

        if config_path.exists():
            with open(config_path) as f:
                config_data = yaml.safe_load(f) or {}

        # Always load API keys from environment
        config_data["api_keys"] = APIKeys.from_env().model_dump()

        return cls(**config_data)

    def save(self, config_path: Path) -> None:
        """Save configuration to YAML file (excluding API keys)."""
        data = self.model_dump(exclude={"api_keys"})

        # Convert Path objects to strings for YAML
        data["output_dir"] = str(data["output_dir"])
        data["config_dir"] = str(data["config_dir"])

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config(config_path: Optional[Path] = None) -> Config:
    """Reload configuration from file."""
    global _config
    _config = Config.load(config_path)
    return _config
