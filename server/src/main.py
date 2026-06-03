"""CLI entry point for Hebrew Democracy Video Pipeline."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import get_config, reload_config
from .pipeline.orchestrator import PipelineOrchestrator, run_test

console = Console()
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging with rich output."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("fal_client").setLevel(logging.WARNING)


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.option(
    "-c", "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file"
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config: Optional[Path]) -> None:
    """Hebrew Democracy Video Pipeline - Generate educational videos."""
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    if config:
        reload_config(config)


@cli.command()
@click.option(
    "--text", "-t",
    required=True,
    help="Hebrew text to convert to speech"
)
@click.option(
    "--image", "-i",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to input image"
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output directory"
)
@click.pass_context
def test(
    ctx: click.Context,
    text: str,
    image: Path,
    output: Optional[Path],
) -> None:
    """Test pipeline with a single text/image pair.

    Example:
        python -m src.main test --text "שלום עולם" --image ./ref.png
    """
    console.print(
        Panel.fit(
            f"[bold blue]Testing Pipeline[/bold blue]\n\n"
            f"Text: {text[:50]}{'...' if len(text) > 50 else ''}\n"
            f"Image: {image}",
            title="Hebrew Video Pipeline",
        )
    )

    async def _run_test():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing...", total=None)

            result = await run_test(
                text=text,
                image_path=image,
                output_dir=output,
            )

            progress.update(task, completed=True)

        return result

    result = asyncio.run(_run_test())

    if result.success:
        console.print("\n[bold green]Success![/bold green]\n")
        console.print(f"Video: {result.video_path}")
        console.print(f"Audio: {result.audio_path}")
        console.print(f"Duration: {result.duration:.2f}s")
    else:
        console.print(f"\n[bold red]Error:[/bold red] {result.error}")
        sys.exit(1)


@cli.command()
@click.option(
    "--topic", "-t",
    default=None,
    help="Topic for the video (not needed if using --brief)"
)
@click.option(
    "--angle", "-a",
    default=None,
    help="Angle/guidelines for the video (not needed if using --brief)"
)
@click.option(
    "--brief", "-b",
    type=click.Path(exists=True, path_type=Path),
    help="Path to content brief file (YAML or Markdown)"
)
@click.option(
    "--image", "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Reference image for character"
)
@click.option(
    "--workflow", "-w",
    type=click.Choice(["1", "2"]),
    default="1",
    help="Workflow to use (1=image-based ~$4.50, 2=video-based ~$6)"
)
@click.option(
    "--preview",
    is_flag=True,
    help="Generate preview (fewer segments, ~$1.50)"
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output directory"
)
@click.option(
    "--llm",
    type=click.Choice(["claude", "gemini"]),
    default=None,
    help="Override LLM provider"
)
@click.pass_context
def generate(
    ctx: click.Context,
    topic: Optional[str],
    angle: Optional[str],
    brief: Optional[Path],
    image: Optional[Path],
    workflow: str,
    preview: bool,
    output: Optional[Path],
    llm: Optional[str],
) -> None:
    """Generate a full video from topic or content brief.

    You can use either simple mode (--topic and --angle) or detailed mode (--brief).

    Simple mode example:
        python -m src.main generate \\
            --topic "government accountability" \\
            --angle "empathetic, solution-focused" \\
            --image ./ref.png

    Detailed mode example (recommended):
        python -m src.main generate \\
            --brief ./briefs/october7_investigation.yaml \\
            --image ./ref.png

    Workflow 1 (Image-based, ~$4.50):
        Uses VEED Fabric for direct image+audio to video with lip-sync.
        Faster and cheaper, good for most use cases.

    Workflow 2 (Video-based, ~$6):
        Uses Kling for image+motion to video, then sync for lip-sync.
        Higher quality motion, better for dynamic content.
    """
    from .schemas import ContentBrief, ScriptRequest

    # Validate input mode
    if brief is None and (topic is None or angle is None):
        console.print("[bold red]Error:[/bold red] Must provide either --brief OR both --topic and --angle")
        sys.exit(1)

    # Load brief if provided
    content_brief = None
    if brief:
        try:
            if brief.suffix in (".yaml", ".yml"):
                content_brief = ContentBrief.from_yaml(brief)
            elif brief.suffix == ".md":
                content_brief = ContentBrief.from_markdown(brief)
            else:
                console.print(f"[bold red]Error:[/bold red] Unsupported brief format: {brief.suffix}")
                sys.exit(1)
            topic = content_brief.title
            angle = f"{content_brief.emotional_tone}, {', '.join(content_brief.rhetorical_devices)}"
        except Exception as e:
            console.print(f"[bold red]Error loading brief:[/bold red] {e}")
            sys.exit(1)
    from .pipeline import Workflow1Pipeline, Workflow2Pipeline

    # Update config if LLM override specified
    if llm:
        config = get_config()
        config.llm.provider = llm

    workflow_name = "Image-based (VEED Fabric)" if workflow == "1" else "Video-based (Kling + Sync)"
    estimated_cost = "~$1.50" if preview else ("~$4.50" if workflow == "1" else "~$6.00")
    mode = "Detailed Brief" if content_brief else "Simple"
    key_points_preview = ""
    if content_brief and content_brief.key_points:
        key_points_preview = f"\nKey Points: {len(content_brief.key_points)} defined"

    console.print(
        Panel.fit(
            f"[bold blue]Generating Video[/bold blue]\n\n"
            f"Mode: {mode}\n"
            f"Topic: {topic}\n"
            f"Angle: {angle}{key_points_preview}\n"
            f"Workflow: {workflow_name}\n"
            f"Preview: {preview}\n"
            f"Est. Cost: {estimated_cost}",
            title="Hebrew Video Pipeline",
        )
    )

    async def _run_generate():
        if workflow == "1":
            pipeline = Workflow1Pipeline()
        else:
            pipeline = Workflow2Pipeline()

        try:
            final_path = await pipeline.run(
                topic=topic,
                angle=angle,
                brief=content_brief,
                output_dir=output,
                preview=preview,
                reference_image=image,
            )
            return final_path
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating video...", total=None)

            final_path = asyncio.run(_run_generate())

            progress.update(task, completed=True)

        console.print("\n[bold green]Success![/bold green]\n")
        console.print(f"Video: {final_path}")
        console.print(f"\nOutput directory: {final_path.parent}")

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show pipeline configuration and status."""
    config = get_config()

    console.print(
        Panel.fit(
            "[bold blue]Pipeline Configuration[/bold blue]",
            title="Hebrew Video Pipeline",
        )
    )

    # API Keys status
    console.print("\n[bold]API Keys:[/bold]")
    keys = {
        "Fal.ai": bool(config.api_keys.fal),
        "Replicate": bool(config.api_keys.replicate),
        "ElevenLabs": bool(config.api_keys.elevenlabs),
        "Anthropic": bool(config.api_keys.anthropic),
        "Google": bool(config.api_keys.google),
    }
    for name, configured in keys.items():
        status = "[green]Configured[/green]" if configured else "[red]Missing[/red]"
        console.print(f"  {name}: {status}")

    # LLM Configuration
    console.print("\n[bold]LLM Configuration:[/bold]")
    console.print(f"  Provider: {config.llm.provider}")
    console.print(f"  Claude Model: {config.llm.claude_model}")
    console.print(f"  Gemini Model: {config.llm.gemini_model}")

    # Video Configuration
    console.print("\n[bold]Video Configuration:[/bold]")
    console.print(f"  Primary: {config.video.primary_provider}")
    console.print(f"  Fallback: {config.video.fallback_provider}")
    console.print(f"  Resolution: {config.video.resolution}")

    # Audio Configuration
    console.print("\n[bold]Audio Configuration:[/bold]")
    console.print(f"  Provider: {config.audio.provider}")
    console.print(f"  Voice: {config.audio.voice_name} ({config.audio.voice_id})")

    # Paths
    console.print("\n[bold]Paths:[/bold]")
    console.print(f"  Output: {config.output_dir}")
    console.print(f"  Config: {config.config_dir}")


@cli.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Check health of all providers."""
    console.print(
        Panel.fit(
            "[bold blue]Health Check[/bold blue]",
            title="Hebrew Video Pipeline",
        )
    )

    async def _check_health():
        config = get_config()
        orchestrator = PipelineOrchestrator(config)

        try:
            await orchestrator.initialize()

            # Check audio provider
            audio_ok = await orchestrator._audio_provider.health_check()
            status = "[green]OK[/green]" if audio_ok else "[red]Failed[/red]"
            console.print(f"  ElevenLabs: {status}")

            # Check video providers
            fal_ok = await orchestrator._video_provider.primary.health_check()
            status = "[green]OK[/green]" if fal_ok else "[red]Failed[/red]"
            console.print(f"  Fal.ai (VEED): {status}")

            replicate_ok = await orchestrator._video_provider.fallback.health_check()
            status = "[green]OK[/green]" if replicate_ok else "[red]Failed[/red]"
            console.print(f"  Replicate (VEED): {status}")

        finally:
            await orchestrator.close()

    asyncio.run(_check_health())


def main() -> None:
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
