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
    required=True,
    help="Topic for the video"
)
@click.option(
    "--angle", "-a",
    default="empathetic, solution-focused",
    help="Angle/guidelines for the video"
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
    help="Workflow to use (1=image-based, 2=video-based)"
)
@click.option(
    "--preview",
    is_flag=True,
    help="Generate preview (fewer segments)"
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output directory"
)
@click.pass_context
def generate(
    ctx: click.Context,
    topic: str,
    angle: str,
    image: Optional[Path],
    workflow: str,
    preview: bool,
    output: Optional[Path],
) -> None:
    """Generate a full video from topic.

    Example:
        python -m src.main generate \\
            --topic "government accountability" \\
            --angle "empathetic, solution-focused" \\
            --image ./ref.png
    """
    console.print(
        Panel.fit(
            f"[bold blue]Generating Video[/bold blue]\n\n"
            f"Topic: {topic}\n"
            f"Angle: {angle}\n"
            f"Workflow: {workflow}\n"
            f"Preview: {preview}",
            title="Hebrew Video Pipeline",
        )
    )

    # TODO: Implement full generation workflow
    console.print(
        "\n[yellow]Full generation not yet implemented.[/yellow]\n"
        "Use 'test' command for single-segment testing."
    )


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
