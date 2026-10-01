"""Command-line interface."""

from __future__ import annotations

import asyncio
import logging
import math
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console, Group
from rich.live import Live
from rich.logging import RichHandler
from rich.markup import escape
from rich.progress import (
    BarColumn,
    DownloadColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from anime_downloader import __version__
from anime_downloader.client import AnimeWorld, FetchError
from anime_downloader.downloader import (
    DownloadReport,
    EpisodeDone,
    EpisodeProgress,
    download_episodes,
)
from anime_downloader.models import Anime, Episode
from anime_downloader.parsers import ParseError, anime_page_url, safe_filename

DEFAULT_JOBS = 3
MAX_JOBS = 16

console = Console(stderr=True)
log = logging.getLogger("anime_downloader")

app = typer.Typer(
    help="Download whole seasons from AnimeWorld, several episodes at a time.",
    add_completion=False,
)


def _stdin_is_tty() -> bool:
    return sys.stdin.isatty()


def _parse_url(value: str) -> str:
    try:
        return anime_page_url(value)
    except ParseError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _parse_jobs(value: str) -> int:
    if not value.strip().isdigit() or not 1 <= int(value) <= MAX_JOBS:
        raise typer.BadParameter(f"expected a number from 1 to {MAX_JOBS}, got {value!r}")
    return int(value)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"anime-downloader {__version__}")
        raise typer.Exit


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, show_path=False)],
        force=True,
    )
    log.setLevel(logging.DEBUG if verbose else logging.INFO)


def _choose_episodes(
    anime: Anime, first: int | None, last: int | None, *, interactive: bool
) -> list[Episode]:
    if not anime.episodes:
        log.error("%s has no episodes to download yet", anime.title)
        raise typer.Exit(1)

    values = [ep.value for ep in anime.episodes if ep.value is not None]
    span = f", {min(values):g} to {max(values):g}" if values else ""
    console.print(f"[bold]{escape(anime.title)}[/]: {len(anime.episodes)} episode(s){span}")
    if interactive and values:
        if first is None:
            first = typer.prompt("Download from episode", default=math.floor(min(values)), type=int)
        if last is None:
            last = typer.prompt("Up to episode", default=math.ceil(max(values)), type=int)

    episodes = anime.select(first, last)
    if not episodes:
        log.error(
            "No episodes numbered between %s and %s",
            "the first" if first is None else first,
            "the last" if last is None else last,
        )
        raise typer.Exit(1)
    return episodes


def _choose_jobs(jobs: int | None, episode_count: int, *, interactive: bool) -> int:
    if jobs is None:
        jobs = DEFAULT_JOBS
        if interactive and episode_count > 1:
            jobs = typer.prompt("Parallel downloads", default=str(jobs), value_proc=_parse_jobs)
    return min(jobs, episode_count)


@contextmanager
def _progress(total: int) -> Iterator[tuple[EpisodeProgress, EpisodeDone]]:
    overall = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    files = Progress(
        TextColumn("  {task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    )
    overall_task = overall.add_task("Episodes", total=total)
    tasks: dict[str, TaskID] = {}

    def on_progress(episode: Episode, done: int, size: int | None) -> None:
        if episode.token not in tasks:
            tasks[episode.token] = files.add_task(f"Episode {episode.number}", total=size)
        files.update(tasks[episode.token], completed=done, total=size)

    def on_done(episode: Episode) -> None:
        if (task := tasks.pop(episode.token, None)) is not None:
            files.remove_task(task)
        overall.advance(overall_task)

    with Live(Group(overall, files), console=console, refresh_per_second=4):
        yield on_progress, on_done


def _summarise(report: DownloadReport, out_dir: Path) -> None:
    parts = [f"downloaded {len(report.downloaded)}"]
    if report.skipped:
        parts.append(f"{len(report.skipped)} already there")
    if report.failed:
        parts.append(f"{len(report.failed)} failed")
    log.info("Done: %s → %s", ", ".join(parts), out_dir)
    if report.failed:
        numbers = ", ".join(episode.number for episode, _ in report.failed)
        log.error("Failed episode(s): %s. Run the same command again to retry them.", numbers)
        raise typer.Exit(1)


async def _run(
    url: str,
    first: int | None,
    last: int | None,
    jobs: int | None,
    out: Path,
    *,
    interactive: bool,
) -> None:
    async with AnimeWorld() as site:
        try:
            with console.status("Reading the anime page…"):
                anime = await site.get_anime(url)
        except (FetchError, ParseError) as exc:
            log.error("Could not read %s: %s", url, exc)
            raise typer.Exit(1) from exc

        episodes = _choose_episodes(anime, first, last, interactive=interactive)
        jobs = _choose_jobs(jobs, len(episodes), interactive=interactive)
        out_dir = out / safe_filename(anime.title)
        console.print(f"{len(episodes)} episode(s), {jobs} at a time → {escape(str(out_dir))}")
        if interactive and not typer.confirm("Start downloading?", default=True):
            raise typer.Exit

        with _progress(len(episodes)) as (on_progress, on_done):
            report = await download_episodes(
                site,
                anime,
                episodes,
                out_dir,
                jobs=jobs,
                on_progress=on_progress,
                on_done=on_done,
            )
    _summarise(report, out_dir)


@app.command()
def main(
    url: Annotated[
        str | None,
        typer.Argument(
            help="Anime or episode link, e.g. https://www.animeworld.ac/play/black-clover-ita.IDsmb",
            show_default=False,
        ),
    ] = None,
    first: Annotated[
        int | None,
        typer.Option(
            "--from",
            "-f",
            min=0,
            help="First episode to download (default: the first)",
            show_default=False,
        ),
    ] = None,
    last: Annotated[
        int | None,
        typer.Option(
            "--to",
            "-t",
            min=0,
            help="Last episode to download (default: the last)",
            show_default=False,
        ),
    ] = None,
    jobs: Annotated[
        int | None,
        typer.Option(
            "--jobs",
            "-j",
            min=1,
            max=MAX_JOBS,
            help=f"Episodes downloaded at the same time (default: {DEFAULT_JOBS})",
            show_default=False,
        ),
    ] = None,
    out: Annotated[
        Path,
        typer.Option(
            "--out", "-o", file_okay=False, help="Download directory, one folder per anime."
        ),
    ] = Path("downloads"),
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Never prompt: without --from/--to, download everything."),
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show debug logging.")] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
        ),
    ] = False,
) -> None:
    """Download episodes of an anime from AnimeWorld.

    Anything you leave out is asked interactively. Interrupted downloads resume
    when you run the same command again.
    """
    _setup_logging(verbose)
    interactive = not yes and _stdin_is_tty()
    if url is not None:
        url = _parse_url(url)
    elif interactive:
        url = typer.prompt("AnimeWorld link", value_proc=_parse_url)
    else:
        raise typer.BadParameter("required when not running in a terminal", param_hint="'URL'")

    try:
        asyncio.run(_run(url, first, last, jobs, out, interactive=interactive))
    except KeyboardInterrupt:
        console.print("\nInterrupted. Run the same command again to resume.")
        raise typer.Exit(130) from None
