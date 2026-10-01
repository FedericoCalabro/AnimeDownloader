"""Download a batch of episodes, a few at a time."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from anime_downloader.client import AnimeWorld, FetchError
from anime_downloader.models import Anime, Episode
from anime_downloader.parsers import ParseError, video_filename

log = logging.getLogger(__name__)

EpisodeProgress = Callable[[Episode, int, int | None], object]
EpisodeDone = Callable[[Episode], object]


@dataclass(slots=True)
class DownloadReport:
    downloaded: list[Path] = field(default_factory=list)
    #: Files that were already complete in the output directory.
    skipped: list[Path] = field(default_factory=list)
    failed: list[tuple[Episode, str]] = field(default_factory=list)


async def download_episodes(
    site: AnimeWorld,
    anime: Anime,
    episodes: Iterable[Episode],
    out_dir: Path,
    *,
    jobs: int = 3,
    on_progress: EpisodeProgress = lambda episode, done, total: None,
    on_done: EpisodeDone = lambda episode: None,
) -> DownloadReport:
    """Download ``episodes`` into ``out_dir``, at most ``jobs`` at the same time.

    Episodes whose file already exists are skipped, so running the same batch
    again picks up where it stopped. A failed episode never stops the others.
    """
    semaphore = asyncio.Semaphore(jobs)

    async def fetch(episode: Episode) -> tuple[Path, bool] | Exception:
        outcome: tuple[Path, bool] | Exception
        async with semaphore:
            try:
                video_url = await site.get_video_url(anime, episode)
                dest = out_dir / video_filename(video_url)
                if dest.exists():
                    outcome = dest, False
                else:
                    await site.download(
                        video_url, dest, lambda done, total: on_progress(episode, done, total)
                    )
                    outcome = dest, True
            except (FetchError, ParseError, httpx.HTTPError, OSError) as exc:
                log.warning("Episode %s failed: %s", episode.number, exc)
                outcome = exc
        # Not in a ``finally``: an interrupted episode must not be reported as done.
        on_done(episode)
        return outcome

    episodes = list(episodes)
    outcomes = await asyncio.gather(*(fetch(episode) for episode in episodes))

    report = DownloadReport()
    for episode, outcome in zip(episodes, outcomes, strict=True):
        if isinstance(outcome, Exception):
            report.failed.append((episode, str(outcome)))
        elif outcome[1]:
            report.downloaded.append(outcome[0])
        else:
            report.skipped.append(outcome[0])
    return report
