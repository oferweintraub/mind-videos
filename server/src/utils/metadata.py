"""Metadata utilities for tracking video generation."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


class MetadataTracker:
    """Track metadata for video generation.

    Handles:
    - Cost tracking per video
    - A/B testing data
    - Generation timestamps
    - Provider usage statistics
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self._metadata: dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "status": "in_progress",
            "costs": {},
            "providers": {},
            "segments": [],
            "ab_testing": {},
            "errors": [],
        }

    def set_topic(self, topic: str, angle: str) -> None:
        """Set the video topic and angle.

        Args:
            topic: Video topic
            angle: Video angle/guidelines
        """
        self._metadata["topic"] = topic
        self._metadata["angle"] = angle

    def add_cost(
        self,
        provider: str,
        operation: str,
        amount: float,
        details: Optional[dict] = None,
    ) -> None:
        """Record a cost incurred.

        Args:
            provider: Provider name (e.g., 'elevenlabs', 'fal')
            operation: Operation type (e.g., 'tts', 'video_generation')
            amount: Cost in USD
            details: Additional details
        """
        if provider not in self._metadata["costs"]:
            self._metadata["costs"][provider] = []

        entry = {
            "operation": operation,
            "amount": amount,
            "timestamp": datetime.now().isoformat(),
        }

        if details:
            entry["details"] = details

        self._metadata["costs"][provider].append(entry)

    def get_total_cost(self) -> float:
        """Get total cost incurred.

        Returns:
            Total cost in USD
        """
        total = 0.0
        for provider_costs in self._metadata["costs"].values():
            for entry in provider_costs:
                total += entry.get("amount", 0)
        return total

    def record_provider_usage(
        self,
        provider: str,
        operation: str,
        success: bool,
        duration: float,
        metadata: Optional[dict] = None,
    ) -> None:
        """Record provider usage for statistics.

        Args:
            provider: Provider name
            operation: Operation type
            success: Whether operation succeeded
            duration: Duration in seconds
            metadata: Additional metadata
        """
        if provider not in self._metadata["providers"]:
            self._metadata["providers"][provider] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_duration": 0.0,
                "operations": {},
            }

        stats = self._metadata["providers"][provider]
        stats["total_calls"] += 1
        stats["total_duration"] += duration

        if success:
            stats["successful_calls"] += 1
        else:
            stats["failed_calls"] += 1

        if operation not in stats["operations"]:
            stats["operations"][operation] = {"count": 0, "successes": 0}

        stats["operations"][operation]["count"] += 1
        if success:
            stats["operations"][operation]["successes"] += 1

    def add_segment_metadata(
        self,
        index: int,
        text: str,
        duration: float,
        audio_path: Optional[str] = None,
        video_path: Optional[str] = None,
        image_path: Optional[str] = None,
        quality_score: Optional[float] = None,
    ) -> None:
        """Add metadata for a segment.

        Args:
            index: Segment index
            text: Segment text
            duration: Segment duration
            audio_path: Path to audio file
            video_path: Path to video file
            image_path: Path to image file
            quality_score: Quality validation score
        """
        segment_data = {
            "index": index,
            "text": text[:100] + "..." if len(text) > 100 else text,
            "duration": duration,
            "audio_path": audio_path,
            "video_path": video_path,
            "image_path": image_path,
            "quality_score": quality_score,
            "created_at": datetime.now().isoformat(),
        }

        # Update or append
        existing = next(
            (s for s in self._metadata["segments"] if s["index"] == index),
            None
        )

        if existing:
            existing.update(segment_data)
        else:
            self._metadata["segments"].append(segment_data)

    def record_ab_testing(
        self,
        options: list[dict],
        selected_option: str,
        selection_reasoning: str,
        selection_method: str = "llm_judge",
    ) -> None:
        """Record A/B testing data.

        Args:
            options: List of script options considered
            selected_option: ID of selected option
            selection_reasoning: Reasoning for selection
            selection_method: Method used for selection
        """
        self._metadata["ab_testing"] = {
            "options": [
                {
                    "id": opt.get("option_id", opt.get("id")),
                    "title": opt.get("title"),
                    "tone": opt.get("tone"),
                    "summary": opt.get("summary"),
                }
                for opt in options
            ],
            "selected_option": selected_option,
            "selection_reasoning": selection_reasoning,
            "selection_method": selection_method,
            "timestamp": datetime.now().isoformat(),
        }

    def record_error(
        self,
        error_type: str,
        message: str,
        recoverable: bool,
        context: Optional[dict] = None,
    ) -> None:
        """Record an error that occurred.

        Args:
            error_type: Type of error
            message: Error message
            recoverable: Whether error was recovered from
            context: Additional context
        """
        error_entry = {
            "type": error_type,
            "message": message,
            "recoverable": recoverable,
            "timestamp": datetime.now().isoformat(),
        }

        if context:
            error_entry["context"] = context

        self._metadata["errors"].append(error_entry)

    def set_output_files(
        self,
        video_path: Optional[Path] = None,
        subtitle_path: Optional[Path] = None,
        thumbnail_paths: Optional[list[Path]] = None,
    ) -> None:
        """Set paths to output files.

        Args:
            video_path: Final video path
            subtitle_path: Subtitle file path
            thumbnail_paths: List of thumbnail paths
        """
        self._metadata["output_files"] = {
            "video": str(video_path) if video_path else None,
            "subtitles": str(subtitle_path) if subtitle_path else None,
            "thumbnails": [str(p) for p in (thumbnail_paths or [])],
        }

    def set_status(
        self,
        status: str,
        message: Optional[str] = None,
    ) -> None:
        """Set generation status.

        Args:
            status: Status (in_progress, completed, failed)
            message: Optional status message
        """
        self._metadata["status"] = status
        self._metadata["updated_at"] = datetime.now().isoformat()

        if message:
            self._metadata["status_message"] = message

    def finalize(
        self,
        success: bool,
        final_video_path: Optional[Path] = None,
        total_duration: Optional[float] = None,
    ) -> None:
        """Finalize metadata after generation complete.

        Args:
            success: Whether generation was successful
            final_video_path: Path to final video
            total_duration: Total video duration
        """
        self._metadata["completed_at"] = datetime.now().isoformat()
        self._metadata["status"] = "completed" if success else "failed"
        self._metadata["success"] = success
        self._metadata["total_cost"] = self.get_total_cost()

        if final_video_path:
            self._metadata["final_video"] = str(final_video_path)

        if total_duration:
            self._metadata["total_duration"] = total_duration

        # Calculate some statistics
        if self._metadata["segments"]:
            self._metadata["segment_count"] = len(self._metadata["segments"])
            durations = [s.get("duration", 0) for s in self._metadata["segments"]]
            self._metadata["average_segment_duration"] = (
                sum(durations) / len(durations) if durations else 0
            )

    def save(self, filename: str = "metadata.yaml") -> Path:
        """Save metadata to YAML file.

        Args:
            filename: Output filename

        Returns:
            Path to saved file
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(
                self._metadata,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

        logger.info(f"Saved metadata to {output_path}")

        return output_path

    def load(self, path: Path) -> dict:
        """Load metadata from YAML file.

        Args:
            path: Path to metadata file

        Returns:
            Loaded metadata dictionary
        """
        with open(path, "r", encoding="utf-8") as f:
            self._metadata = yaml.safe_load(f)

        return self._metadata

    def to_dict(self) -> dict:
        """Get metadata as dictionary.

        Returns:
            Metadata dictionary
        """
        return self._metadata.copy()
