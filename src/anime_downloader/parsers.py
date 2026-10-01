"""Pure functions that turn AnimeWorld URLs, HTML and API payloads into data.

Nothing in this module performs I/O, which keeps it fully testable offline
against saved HTML fixtures (see ``tests/fixtures``).
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from anime_downloader.models import Anime, Episode

#: The site's own server, the only one whose episodes resolve to a direct video link.
ANIMEWORLD_SERVER = "9"

_PLAY_PATH = re.compile(r"^/play/(?P<anime>[^/]+\.[^/]+)(?:/[^/]+)?/?$")
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ParseError(ValueError):
    """Raised when a URL, page or API response does not look like what we expect."""


def _text(node: LexborNode | None) -> str:
    return " ".join(node.text(separator=" ").split()) if node is not None else ""


def _attr(node: LexborNode, name: str) -> str:
    return (node.attributes.get(name) or "").strip()


def anime_page_url(url: str) -> str:
    """Validate an anime or episode URL and return the anime page URL.

    Any AnimeWorld domain is accepted (the site moves between them), with or
    without an episode token and with or without a scheme.
    """
    url = url.strip()
    if "://" not in url:
        url = f"https://{url}"
    parts = urlsplit(url)
    match = _PLAY_PATH.match(parts.path)
    if parts.scheme not in {"http", "https"} or not parts.netloc or match is None:
        raise ParseError(f"expected a link like https://www.animeworld.ac/play/<anime>, got {url}")
    return f"https://{parts.netloc}/play/{match['anime']}"


def parse_anime(html: str, url: str) -> Anime:
    """Parse an anime page into its title and episode list."""
    tree = LexborHTMLParser(html)
    title = _text(tree.css_first("h1#anime-title"))
    if not title:
        raise ParseError(f"No anime found on page: {url}")

    episodes: dict[str, Episode] = {}
    for link in tree.css(f'.server[data-name="{ANIMEWORLD_SERVER}"] li.episode a'):
        token = _attr(link, "data-id")
        number = _attr(link, "data-episode-num") or _text(link)
        if token and number:
            episodes.setdefault(token, Episode(number=number, token=token))
    return Anime(title=title, url=url, episodes=tuple(episodes.values()))


def parse_video_url(payload: Any) -> str:
    """Extract the direct video link from an ``/api/episode/info`` response."""
    grabber = payload.get("grabber") if isinstance(payload, dict) else None
    if not isinstance(grabber, str) or urlsplit(grabber).scheme not in {"http", "https"}:
        raise ParseError(f"No direct video link in episode info: {payload!r}")
    return grabber


def safe_filename(name: str) -> str:
    """``name`` with characters that some filesystems reject replaced by ``_``."""
    return _UNSAFE_CHARS.sub("_", name).strip().rstrip(". ") or "_"


def video_filename(video_url: str) -> str:
    """Local filename for a video, taken from its URL, e.g. ``BlackClover_Ep_01_ITA.mp4``."""
    return safe_filename(unquote(PurePosixPath(urlsplit(video_url).path).name))
