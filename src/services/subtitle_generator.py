"""Subtitle generator service for Hebrew SRT files."""

import logging
import re
from pathlib import Path
from typing import Optional

from ..config import Config, get_config
from ..schemas import Segment, SegmentList

logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """Service for generating Hebrew subtitles.

    Handles:
    - SRT file generation from segments
    - Hebrew RTL encoding
    - Timing synchronization
    - Style customization
    """

    def __init__(
        self,
        config: Optional[Config] = None,
    ):
        self.config = config or get_config()

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds to SRT timestamp (HH:MM:SS,mmm).

        Args:
            seconds: Time in seconds

        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _prepare_hebrew_text(self, text: str) -> str:
        """Prepare Hebrew text for subtitle display.

        Args:
            text: Hebrew text

        Returns:
            Text prepared for RTL display
        """
        # Clean whitespace
        text = " ".join(text.split())

        # Add RTL mark at start for proper rendering
        rtl_mark = "\u200F"

        # Split into lines if too long (max ~40 chars per line for readability)
        max_line_length = 40
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_length = len(word)
            if current_length + word_length + 1 > max_line_length and current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
            else:
                current_line.append(word)
                current_length += word_length + 1

        if current_line:
            lines.append(" ".join(current_line))

        # Add RTL mark to each line
        return "\n".join([f"{rtl_mark}{line}" for line in lines])

    def _split_text_for_timing(
        self,
        text: str,
        duration: float,
        max_chars_per_subtitle: int = 80,
    ) -> list[tuple[str, float, float]]:
        """Split text into timed subtitle chunks.

        Args:
            text: Full text
            duration: Total duration in seconds
            max_chars_per_subtitle: Max characters per subtitle

        Returns:
            List of (text, start_time, end_time) tuples
        """
        # Split into sentences or chunks
        sentences = re.split(r'([.!?])\s*', text)

        # Recombine sentences with their punctuation
        chunks = []
        i = 0
        while i < len(sentences):
            chunk = sentences[i]
            if i + 1 < len(sentences) and len(sentences[i + 1]) == 1:
                chunk += sentences[i + 1]
                i += 2
            else:
                i += 1
            if chunk.strip():
                chunks.append(chunk.strip())

        if not chunks:
            chunks = [text]

        # Calculate timing based on character count
        total_chars = sum(len(c) for c in chunks)
        char_duration = duration / total_chars if total_chars > 0 else duration

        result = []
        current_time = 0.0

        for chunk in chunks:
            chunk_duration = len(chunk) * char_duration
            # Ensure minimum subtitle duration
            chunk_duration = max(chunk_duration, 1.0)

            start_time = current_time
            end_time = min(current_time + chunk_duration, duration)

            result.append((chunk, start_time, end_time))
            current_time = end_time

        return result

    def generate_srt(
        self,
        segments: SegmentList,
        output_path: Path,
        use_actual_durations: bool = True,
    ) -> Path:
        """Generate SRT subtitle file from segments.

        Args:
            segments: SegmentList with text and timing
            output_path: Path to save SRT file
            use_actual_durations: Use actual audio/video durations if available

        Returns:
            Path to generated SRT file
        """
        srt_entries = []
        entry_index = 1
        cumulative_time = 0.0

        for segment in segments.segments:
            # Get segment duration
            if use_actual_durations and segment.audio_duration:
                duration = segment.audio_duration
            elif use_actual_durations and segment.video_duration:
                duration = segment.video_duration
            else:
                duration = segment.duration_estimate

            # Split text into timed chunks
            chunks = self._split_text_for_timing(segment.text, duration)

            for chunk_text, chunk_start, chunk_end in chunks:
                # Adjust times to cumulative
                start_time = cumulative_time + chunk_start
                end_time = cumulative_time + chunk_end

                # Format text for RTL
                formatted_text = self._prepare_hebrew_text(chunk_text)

                # Create SRT entry
                entry = (
                    f"{entry_index}\n"
                    f"{self._format_timestamp(start_time)} --> "
                    f"{self._format_timestamp(end_time)}\n"
                    f"{formatted_text}\n"
                )
                srt_entries.append(entry)
                entry_index += 1

            cumulative_time += duration

        # Write SRT file with UTF-8 BOM for Hebrew
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(srt_entries))

        logger.info(f"Generated SRT with {entry_index - 1} entries: {output_path}")

        return output_path

    def generate_ass(
        self,
        segments: SegmentList,
        output_path: Path,
        use_actual_durations: bool = True,
    ) -> Path:
        """Generate ASS (Advanced SubStation Alpha) subtitle file.

        ASS format allows for more styling options than SRT.

        Args:
            segments: SegmentList with text and timing
            output_path: Path to save ASS file
            use_actual_durations: Use actual durations if available

        Returns:
            Path to generated ASS file
        """
        subtitle_config = self.config.subtitle

        # ASS header with Hebrew RTL support
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{subtitle_config.font},{subtitle_config.font_size * 2},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,{subtitle_config.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []
        cumulative_time = 0.0

        for segment in segments.segments:
            # Get duration
            if use_actual_durations and segment.audio_duration:
                duration = segment.audio_duration
            elif use_actual_durations and segment.video_duration:
                duration = segment.video_duration
            else:
                duration = segment.duration_estimate

            # Split text into chunks
            chunks = self._split_text_for_timing(segment.text, duration)

            for chunk_text, chunk_start, chunk_end in chunks:
                start_time = cumulative_time + chunk_start
                end_time = cumulative_time + chunk_end

                # Format ASS timestamp
                def format_ass_time(seconds: float) -> str:
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = seconds % 60
                    return f"{hours}:{minutes:02d}:{secs:05.2f}"

                start_str = format_ass_time(start_time)
                end_str = format_ass_time(end_time)

                # Prepare text (ASS uses different line break)
                text = chunk_text.replace("\n", "\\N")

                event = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}"
                events.append(event)

            cumulative_time += duration

        # Write ASS file
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8-sig") as f:
            f.write(header)
            f.write("\n".join(events))

        logger.info(f"Generated ASS subtitle file: {output_path}")

        return output_path

    def get_ffmpeg_subtitle_filter(
        self,
        subtitle_path: Path,
        force_style: bool = True,
    ) -> str:
        """Get FFMPEG filter string for burning subtitles.

        Args:
            subtitle_path: Path to SRT or ASS file
            force_style: Apply style override

        Returns:
            FFMPEG filter string
        """
        subtitle_config = self.config.subtitle

        # Escape path for FFMPEG
        escaped_path = str(subtitle_path).replace(":", "\\:").replace("'", "\\'")

        if subtitle_path.suffix.lower() == ".ass":
            # ASS has its own styling
            return f"ass='{escaped_path}'"

        # SRT with style override
        if force_style:
            style = (
                f"FontName={subtitle_config.font},"
                f"FontSize={subtitle_config.font_size},"
                f"PrimaryColour=&H00FFFFFF,"
                f"OutlineColour=&H00000000,"
                f"BackColour=&H80000000,"
                f"Outline=2,"
                f"Shadow=1,"
                f"MarginV={subtitle_config.margin_v}"
            )
            return f"subtitles='{escaped_path}':force_style='{style}'"

        return f"subtitles='{escaped_path}'"
