from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from anime_downloader import client as client_module
from anime_downloader.client import AnimeWorld
from anime_downloader.parsers import parse_anime

FIXTURES = Path(__file__).parent / "fixtures"
ANIME_HOST = "www.animeworld.ac"
ANIME_URL = f"https://{ANIME_HOST}/play/black-clover-ita.IDsmb"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


BLACK_CLOVER = parse_anime(load_fixture("anime_black-clover-ita.html"), ANIME_URL)


def serve_video(request: httpx.Request, data: bytes, *, drop_after: int | None = None):
    """Answer like a real file server, honouring ``Range``; optionally drop the connection."""
    start, status = 0, 200
    headers = {"Content-Length": str(len(data))}
    if requested := request.headers.get("Range"):
        start = int(requested.removeprefix("bytes=").removesuffix("-"))
        if start >= len(data):
            return httpx.Response(416, headers={"Content-Range": f"bytes */{len(data)}"})
        status = 206
        headers = {
            "Content-Length": str(len(data) - start),
            "Content-Range": f"bytes {start}-{len(data) - 1}/{len(data)}",
        }
    body = data[start:]
    if drop_after is None:
        return httpx.Response(status, headers=headers, content=body)

    async def dropping() -> AsyncIterator[bytes]:
        yield body[:drop_after]
        raise httpx.ReadError("connection reset by peer")

    return httpx.Response(status, headers=headers, content=dropping())


class FakeAnimeWorld:
    """Plays AnimeWorld behind an ``httpx.MockTransport``: the old domain redirecting to the
    current one, the Black Clover page, the episode API and a video server.

    Only episodes listed in ``videos`` (token → bytes) resolve; the API rejects the others.
    """

    def __init__(self, videos: dict[str, bytes]):
        self.videos = videos
        self.page = load_fixture("anime_black-clover-ita.html")
        self.drop_after: dict[str, int] = {}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = request.url
        if url.host == "www.animeworld.so":
            return httpx.Response(301, headers={"Location": str(url.copy_with(host=ANIME_HOST))})
        if url.host == ANIME_HOST and url.path.startswith("/play/"):
            return httpx.Response(200, text=self.page)
        if url.host == ANIME_HOST and url.path == "/api/episode/info":
            token = url.params["id"]
            if token not in self.videos:
                return httpx.Response(401, json={"error": True})
            return httpx.Response(200, json={"grabber": f"https://cdn.test/DDL/{token}.mp4"})
        if url.host == "cdn.test":
            token = url.path.removeprefix("/DDL/").removesuffix(".mp4")
            return serve_video(
                request, self.videos[token], drop_after=self.drop_after.pop(token, None)
            )
        return httpx.Response(404)

    def client(self, **kwargs) -> AnimeWorld:
        return AnimeWorld(transport=httpx.MockTransport(self), **kwargs)


def video_bytes(episode_number: int) -> bytes:
    return bytes([episode_number]) * 5_000


@pytest.fixture
def fake_site() -> FakeAnimeWorld:
    """Fake site where Black Clover episodes 1-3 can be downloaded."""
    return FakeAnimeWorld(
        {ep.token: video_bytes(int(ep.number)) for ep in BLACK_CLOVER.episodes[:3]}
    )


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    """Record retry back-offs instead of actually waiting."""
    recorded: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)
    return recorded
