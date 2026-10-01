"""Async HTTP client for AnimeWorld: anime pages, the episode API and video files.

The episode API (``/api/episode/info?id=<token>``) answers with a direct
``.mp4`` link per episode. Links of the same anime can live on different file
servers, so each episode is always resolved on its own.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from types import TracebackType
from typing import Self

import httpx

from anime_downloader import __version__
from anime_downloader.models import Anime, Episode
from anime_downloader.parsers import ParseError, anime_page_url, parse_anime, parse_video_url

log = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_BACKOFF = 30.0

ByteProgress = Callable[[int, int | None], object]


class FetchError(RuntimeError):
    """Raised when a request fails for good. ``status`` is the last HTTP status, if any."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _check(response: httpx.Response) -> None:
    if not response.is_success:
        status = response.status_code
        raise FetchError(f"HTTP {status} for {response.url}", status=status)


def _total_size(response: httpx.Response) -> int | None:
    """Full size of the file behind ``response``, whether or not it is a range response."""
    if content_range := response.headers.get("Content-Range"):
        total = content_range.rpartition("/")[2]
        return int(total) if total.isdigit() else None
    length = response.headers.get("Content-Length", "")
    return int(length) if length.isdigit() else None


def _noop(done: int, total: int | None) -> None:
    pass


class AnimeWorld:
    """Retrying client for AnimeWorld. Use as an async context manager::

    async with AnimeWorld() as site:
        anime = await site.get_anime("https://www.animeworld.ac/play/black-clover-ita.IDsmb")
        url = await site.get_video_url(anime, anime.episodes[0])
        await site.download(url, Path("episode.mp4"))
    """

    def __init__(
        self,
        *,
        retries: int = 5,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._retries = retries
        self._timeout = timeout
        self._transport = transport
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._http = httpx.AsyncClient(
            follow_redirects=True,
            timeout=self._timeout,
            headers={"User-Agent": f"anime-downloader/{__version__}"},
            transport=self._transport,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("AnimeWorld must be used as an async context manager")
        return self._http

    async def get_anime(self, url: str) -> Anime:
        """Fetch an anime (or episode) page and parse its title and episode list."""
        response = await self._get(anime_page_url(url))
        return parse_anime(response.text, str(response.url))

    async def get_video_url(self, anime: Anime, episode: Episode) -> str:
        """Resolve ``episode`` to its direct video link."""
        api = httpx.URL(anime.url).join("/api/episode/info")
        response = await self._get(api, params={"id": episode.token, "alt": "0"})
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ParseError(f"Episode info for {episode.token} is not JSON") from exc
        return parse_video_url(payload)

    async def download(self, url: str, dest: Path, on_progress: ByteProgress = _noop) -> None:
        """Stream ``url`` into ``dest``, resuming a previous partial download if present.

        Bytes go to ``<dest>.part``, which is renamed to ``dest`` only once complete,
        so an existing ``dest`` is always a finished file.
        """
        part = dest.with_name(f"{dest.name}.part")
        dest.parent.mkdir(parents=True, exist_ok=True)
        await self._retrying(url, lambda: self._download_once(url, part, on_progress))
        part.replace(dest)

    async def _get(
        self, url: str | httpx.URL, params: Mapping[str, str] | None = None
    ) -> httpx.Response:
        async def once() -> httpx.Response:
            response = await self._client.get(url, params=params)
            _check(response)
            return response

        return await self._retrying(str(url), once)

    async def _download_once(self, url: str, part: Path, on_progress: ByteProgress) -> None:
        offset = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else None
        async with self._client.stream("GET", url, headers=headers) as response:
            total = _total_size(response)
            if response.status_code == 416 and total == offset:
                return  # A previous run got every byte but stopped before renaming.
            _check(response)
            if response.status_code != 206:
                offset = 0  # The server ignored the range: start over.
            on_progress(offset, total)
            with part.open("ab" if offset else "wb") as file:
                async for chunk in response.aiter_bytes():
                    file.write(chunk)
                    offset += len(chunk)
                    on_progress(offset, total)
        if total is not None and offset < total:
            raise httpx.RemoteProtocolError(f"connection closed at {offset} of {total} bytes")

    async def _retrying[T](self, what: str, attempt: Callable[[], Awaitable[T]]) -> T:
        error: Exception | None = None
        for number in range(1, self._retries + 1):
            try:
                return await attempt()
            except httpx.TransportError as exc:
                error = exc
            except FetchError as exc:
                if exc.status not in RETRY_STATUSES:
                    raise
                error = exc

            if number < self._retries:
                backoff = min(2.0**number, MAX_BACKOFF)
                log.debug(
                    "Attempt %d for %s failed (%s), retry in %gs", number, what, error, backoff
                )
                await asyncio.sleep(backoff)

        raise FetchError(
            f"Giving up on {what} after {self._retries} attempts: {error}",
            status=getattr(error, "status", None),
        ) from error
