"""Generate Government Accountability video with nursery metaphor.

This script generates a 3-segment video with predefined Hebrew text
and per-segment emotions:
- Segment 1 (serious): The metaphor setup
- Segment 2 (urgent): The pivot
- Segment 3 (angry): The conclusion

Usage:
    python -m scripts.generate_accountability_video --image ./ref.png
    python -m scripts.generate_accountability_video --image ./ref.png --test-audio
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
logger = logging.getLogger(__name__)


# Predefined segments with Hebrew text and emotions
SEGMENTS = [
    {
        "index": 0,
        "text": """תדמיינו גננת שהשאירה את השער פתוח לרווחה. נכנס פורץ, חטף חצי מהגן, והשאיר אחריו הרס וילדים מבוהלים.

ואז? הגננת עומדת מול ההורים ומכריזה בלי למצמץ: "אין בעיה. ברור שכולם אשמים – השומר, העירייה, כולם חוץ ממני. אבל אל תדאגו, אני אחקור בעצמי עד שהכל יתברר".""",
        "emotion": "serious",
        "purpose": "המטאפורה - לספר כסיפור מתח/אימה קצר, להתחיל לאט",
        "image_prompt": "Israeli woman in her 40s sitting on a comfortable sofa, speaking calmly with serious expression, professional portrait, soft natural lighting",
        "camera_angle": "medium",
        "expression": "serious",
        "duration_estimate": 15.0,
    },
    {
        "index": 1,
        "text": """עם יד על הלב – הייתם שולחים את הילדים שלכם לגן הזה מחר בבוקר? הייתם סומכים על הגננת הזו?

זה בדיוק, אבל בדיוק, מה שממשלת ישראל עושה לנו. מי שאחראי למחדל הביטחוני הגדול בתולדותינו, רוצה לחקור את עצמו. זה לא רק אבסורד, זו סכנה קיומית.""",
        "emotion": "urgent",
        "purpose": "שאלת המחץ - להסתכל ישר למצלמה, פאוזה לפני ואחרי",
        "image_prompt": "Israeli woman in her 40s looking directly at camera with urgent expression, hand on heart gesture, professional portrait, dramatic lighting",
        "camera_angle": "medium",
        "expression": "passionate",
        "duration_estimate": 15.0,
    },
    {
        "index": 2,
        "text": """אחרי כמעט שנתיים וחצי, אי אפשר לתת לחתול לשמור על השמנת. כדי לתקן, חייבים אמת. ורק ועדת חקירה ממלכתית תביא אותה.""",
        "emotion": "angry",
        "purpose": "הסיום - קצב מהיר יותר, כועס יותר, נחרץ",
        "image_prompt": "Israeli woman in her 40s close-up portrait shot, intense angry determined expression, professional portrait, dramatic side lighting",
        "camera_angle": "close_up",
        "expression": "determined",
        "duration_estimate": 12.0,
    },
]


def setup_logging(verbose: bool = False) -> None:
    """Configure logging with rich output."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("fal_client").setLevel(logging.WARNING)


async def test_audio_only(output_dir: Path):
    """Test audio generation with emotions for each segment."""
    from src.config import get_config
    from src.providers.audio import ElevenLabsProvider
    from src.utils import preprocess_for_lipsync

    config = get_config()

    audio_provider = ElevenLabsProvider(
        api_key=config.api_keys.elevenlabs,
        voice_id=config.audio.voice_id,
        model_id=config.audio.model_id,
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    console.print("\n[bold]Testing audio generation with emotions:[/bold]\n")

    total_duration = 0.0

    for segment in SEGMENTS:
        audio_path = output_dir / f"segment_{segment['index']:02d}_audio.mp3"

        console.print(f"Segment {segment['index'] + 1}: [cyan]{segment['emotion']}[/cyan]")
        console.print(f"  Text: {segment['text'][:60]}...")

        audio_bytes, duration = await audio_provider.generate_speech(
            text=segment["text"],
            emotion=segment["emotion"],
        )

        # Apply preprocessing
        if config.audio_preprocessing.enabled:
            audio_bytes = await preprocess_for_lipsync(
                audio_input=audio_bytes,
                output_path=audio_path,
                normalize=config.audio_preprocessing.normalize,
                trim=config.audio_preprocessing.trim_silence,
                target_lufs=config.audio_preprocessing.normalize_lufs,
                sample_rate=config.audio_preprocessing.sample_rate,
            )
        else:
            audio_path.write_bytes(audio_bytes)

        total_duration += duration
        console.print(f"  Duration: [green]{duration:.2f}s[/green]")
        console.print(f"  Saved: {audio_path}\n")

    console.print(f"[bold]Total audio duration: {total_duration:.2f}s[/bold]")

    await audio_provider.close()

    return total_duration


async def generate_images(output_dir: Path, reference_image_path: Optional[Path] = None):
    """Generate 3 images for the video segments."""
    from src.config import get_config
    from src.providers.image import NanoBananaProvider

    config = get_config()

    image_provider = NanoBananaProvider(
        api_key=config.api_keys.google,
        model=config.image.model,
        aspect_ratio=config.image.aspect_ratio,
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    console.print("\n[bold]Generating images for each segment:[/bold]\n")

    image_paths = []

    for segment in SEGMENTS:
        image_path = output_dir / f"segment_{segment['index']:02d}_image.png"

        console.print(f"Segment {segment['index'] + 1}: [cyan]{segment['expression']}[/cyan]")
        console.print(f"  Prompt: {segment['image_prompt'][:60]}...")

        image_bytes, metadata = await image_provider.generate_character_image(
            prompt=segment["image_prompt"],
            expression=segment["expression"],
            camera_angle=segment["camera_angle"],
            output_path=image_path,
        )

        image_paths.append(image_path)
        console.print(f"  Saved: {image_path}\n")

    await image_provider.close()

    return image_paths


async def generate_video(
    output_dir: Path,
    reference_image_path: Optional[Path] = None,
    skip_images: bool = False,
    skip_audio: bool = False,
):
    """Generate the full video with all segments."""
    from src.config import get_config
    from src.providers import FallbackProvider
    from src.providers.audio import ElevenLabsProvider
    from src.providers.image import NanoBananaProvider
    from src.providers.video import VideoResolution
    from src.providers.video.fal import VeedFabricFalProvider
    from src.providers.video.replicate import VeedFabricReplicateProvider
    from src.schemas import CameraAngle, Expression, Lighting, SceneDefinition, Segment, SegmentList
    from src.utils import (
        MetadataTracker,
        add_subtitles,
        concatenate_with_smart_transitions,
        TransitionConfig,
        TransitionType,
        preprocess_for_lipsync,
    )
    from src.services import SubtitleGenerator

    config = get_config()
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = MetadataTracker(output_dir)
    metadata.set_topic("Government Accountability", "nursery metaphor, empathetic")

    # Initialize providers
    audio_provider = ElevenLabsProvider(
        api_key=config.api_keys.elevenlabs,
        voice_id=config.audio.voice_id,
        model_id=config.audio.model_id,
    )

    image_provider = NanoBananaProvider(
        api_key=config.api_keys.google,
        model=config.image.model,
        aspect_ratio=config.image.aspect_ratio,
    )

    resolution = VideoResolution(config.video.resolution)
    fal_provider = VeedFabricFalProvider(
        api_key=config.api_keys.fal,
        resolution=resolution,
    )
    replicate_provider = VeedFabricReplicateProvider(
        api_key=config.api_keys.replicate,
        resolution=resolution,
    )
    video_provider = FallbackProvider(
        primary=fal_provider,
        fallback=replicate_provider,
    )

    # Create Segment objects
    segments = []
    for seg_data in SEGMENTS:
        segment = Segment(
            index=seg_data["index"],
            text=seg_data["text"],
            duration_estimate=seg_data["duration_estimate"],
            scene=SceneDefinition(
                camera_angle=CameraAngle(seg_data["camera_angle"]),
                lighting=Lighting.STUDIO,
                expression=Expression(seg_data["expression"]),
                setting="Professional studio setting",
            ),
            purpose=seg_data["purpose"],
        )
        segments.append(segment)

    segment_list = SegmentList(segments=segments)

    # Step 1: Generate images (or skip if already done)
    console.print("\n[bold blue]Step 1: Images[/bold blue]")
    for segment, seg_data in zip(segments, SEGMENTS):
        image_path = output_dir / f"segment_{segment.index:02d}_image.png"

        if skip_images and image_path.exists():
            console.print(f"  Using existing image: {image_path}")
            segment.image_path = str(image_path)
        else:
            console.print(f"  Generating image for segment {segment.index + 1}...")
            image_bytes, _ = await image_provider.generate_character_image(
                prompt=seg_data["image_prompt"],
                expression=seg_data["expression"],
                camera_angle=seg_data["camera_angle"],
                output_path=image_path,
            )
            segment.image_path = str(image_path)
            console.print(f"  Saved: {image_path}")

    # Step 2: Generate audio with emotions
    console.print("\n[bold blue]Step 2: Audio[/bold blue]")
    for segment, seg_data in zip(segments, SEGMENTS):
        audio_path = output_dir / f"segment_{segment.index:02d}_audio.mp3"

        if skip_audio and audio_path.exists():
            console.print(f"  Using existing audio: {audio_path}")
            segment.audio_path = str(audio_path)
            # Get duration from existing file
            from mutagen.mp3 import MP3
            audio = MP3(str(audio_path))
            segment.audio_duration = audio.info.length
        else:
            console.print(f"  Generating audio for segment {segment.index + 1} with emotion [cyan]{seg_data['emotion']}[/cyan]...")

            audio_bytes, duration = await audio_provider.generate_speech(
                text=segment.text,
                emotion=seg_data["emotion"],
            )

            # Apply preprocessing
            if config.audio_preprocessing.enabled:
                audio_bytes = await preprocess_for_lipsync(
                    audio_input=audio_bytes,
                    output_path=audio_path,
                    normalize=config.audio_preprocessing.normalize,
                    trim=config.audio_preprocessing.trim_silence,
                    target_lufs=config.audio_preprocessing.normalize_lufs,
                    sample_rate=config.audio_preprocessing.sample_rate,
                )
            else:
                audio_path.write_bytes(audio_bytes)

            segment.audio_path = str(audio_path)
            segment.audio_duration = duration
            console.print(f"  Duration: {duration:.2f}s")

            metadata.add_cost(
                provider="elevenlabs",
                operation="tts",
                amount=duration / 60 * 0.30,
                details={"duration": duration, "segment": segment.index},
            )

    # Step 3: Generate videos with VEED Fabric
    console.print("\n[bold blue]Step 3: Video Generation[/bold blue]")
    for segment in segments:
        video_path = output_dir / f"segment_{segment.index:02d}_video.mp4"

        console.print(f"  Generating video for segment {segment.index + 1}...")

        image_bytes = Path(segment.image_path).read_bytes()
        audio_bytes = Path(segment.audio_path).read_bytes()

        result = await video_provider.execute(
            "generate_video",
            image=image_bytes,
            audio=audio_bytes,
            output_path=video_path,
        )

        if not result.success:
            raise result.error or Exception(f"Video generation failed for segment {segment.index}")

        video_bytes, video_metadata = result.data
        segment.video_path = str(video_path)
        segment.video_duration = video_metadata.get("duration") or segment.audio_duration

        console.print(f"  Video duration: {segment.video_duration:.2f}s")

        metadata.add_cost(
            provider=video_metadata.get("provider", "fal"),
            operation="video_generation",
            amount=segment.video_duration * 0.08,
            details={"duration": segment.video_duration, "segment": segment.index},
        )

    # Step 4: Concatenate with sequential transitions
    console.print("\n[bold blue]Step 4: Concatenation[/bold blue]")

    video_paths = [Path(s.video_path) for s in segments]
    concatenated_path = output_dir / "video_raw.mp4"

    await concatenate_with_smart_transitions(
        video_paths=video_paths,
        output_path=concatenated_path,
        same_scene_indices=[],  # All scene changes (different images)
        same_scene_transition=TransitionConfig(
            type=TransitionType.FADE,
            duration=config.transitions.same_scene_duration,
            audio_crossfade=config.transitions.audio_crossfade,
            audio_gap=config.transitions.audio_gap,
            audio_fade_duration=config.transitions.audio_fade_duration,
            audio_curve=config.transitions.audio_curve,
        ),
        scene_change_transition=TransitionConfig(
            type=TransitionType.FADE,
            duration=config.transitions.default_duration,
            audio_crossfade=config.transitions.audio_crossfade,
            audio_gap=config.transitions.audio_gap,
            audio_fade_duration=config.transitions.audio_fade_duration,
            audio_curve=config.transitions.audio_curve,
        ),
    )

    console.print(f"  Concatenated: {concatenated_path}")

    # Step 5: Add subtitles
    console.print("\n[bold blue]Step 5: Subtitles[/bold blue]")

    subtitle_generator = SubtitleGenerator(config)
    subtitle_path = output_dir / "subtitles.srt"
    subtitle_generator.generate_srt(
        segments=segment_list,
        output_path=subtitle_path,
    )

    final_path = output_dir / "video.mp4"
    await add_subtitles(
        video_path=concatenated_path,
        subtitle_path=subtitle_path,
        output_path=final_path,
        burn_in=True,
    )

    console.print(f"  Final video: {final_path}")

    # Finalize
    from src.utils.ffmpeg import get_video_info
    video_info = await get_video_info(final_path)

    metadata.set_output_files(
        video_path=final_path,
        subtitle_path=subtitle_path,
        thumbnail_paths=[],
    )
    metadata.finalize(
        success=True,
        final_video_path=final_path,
        total_duration=video_info.get("duration"),
    )
    metadata.save()

    # Cleanup
    await audio_provider.close()
    await image_provider.close()
    await fal_provider.close()
    await replicate_provider.close()

    return final_path, metadata.get_total_cost()


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Government Accountability Video Generator."""
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output directory"
)
def test_audio(output: Optional[Path]) -> None:
    """Test audio generation with emotions only."""
    if output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path(f"output/accountability_test_{timestamp}")

    console.print(
        Panel.fit(
            "[bold blue]Testing Audio with Emotions[/bold blue]\n\n"
            "Segment 1: serious\n"
            "Segment 2: urgent\n"
            "Segment 3: angry",
            title="Accountability Video",
        )
    )

    duration = asyncio.run(test_audio_only(output))
    console.print(f"\n[bold green]Audio test complete![/bold green]")
    console.print(f"Output: {output}")


@cli.command()
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output directory"
)
def images(output: Optional[Path]) -> None:
    """Generate images only."""
    if output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path(f"output/accountability_images_{timestamp}")

    console.print(
        Panel.fit(
            "[bold blue]Generating Images[/bold blue]",
            title="Accountability Video",
        )
    )

    image_paths = asyncio.run(generate_images(output))
    console.print(f"\n[bold green]Images generated![/bold green]")
    for path in image_paths:
        console.print(f"  {path}")


@cli.command()
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output directory"
)
@click.option(
    "--image", "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Reference image for character consistency"
)
@click.option(
    "--skip-images",
    is_flag=True,
    help="Skip image generation (use existing)"
)
@click.option(
    "--skip-audio",
    is_flag=True,
    help="Skip audio generation (use existing)"
)
def generate(
    output: Optional[Path],
    image: Optional[Path],
    skip_images: bool,
    skip_audio: bool,
) -> None:
    """Generate the full video."""
    if output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path(f"output/accountability_{timestamp}")

    console.print(
        Panel.fit(
            "[bold blue]Generating Accountability Video[/bold blue]\n\n"
            "3 segments with:\n"
            "  1. serious emotion (18s)\n"
            "  2. urgent emotion (16s)\n"
            "  3. angry emotion (16s)\n\n"
            f"Estimated cost: ~$4.30",
            title="Government Accountability",
        )
    )

    try:
        final_path, total_cost = asyncio.run(
            generate_video(output, image, skip_images, skip_audio)
        )

        console.print(f"\n[bold green]Success![/bold green]")
        console.print(f"Video: {final_path}")
        console.print(f"Total cost: ${total_cost:.2f}")

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise


def main() -> None:
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
