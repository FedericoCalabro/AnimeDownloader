import asyncio

import httpx
import pytest
from conftest import ANIME_HOST, BLACK_CLOVER, video_bytes

from anime_downloader.client import AnimeWorld, FetchError

FIRST = BLACK_CLOVER.episodes[0]


def run(site, coro_factory):
    async def go():
        async with site.client(retries=3) as client:
            return await coro_factory(client)

    return asyncio.run(go())


def test_get_anime_follows_the_site_to_its_current_domain(fake_site):
    anime = run(
        fake_site,
        lambda c: c.get_anime("https://www.animeworld.so/play/black-clover-ita.IDsmb/SuNI0S"),
    )

    assert anime.url == f"https://{ANIME_HOST}/play/black-clover-ita.IDsmb"
    assert len(anime.episodes) == 120


def test_get_video_url_asks_the_episode_api_on_the_current_domain(fake_site):
    url = run(fake_site, lambda c: c.get_video_url(BLACK_CLOVER, FIRST))

    assert url == f"https://cdn.test/DDL/{FIRST.token}.mp4"
    request = fake_site.requests[-1]
    assert request.url.host == ANIME_HOST
    assert dict(request.url.params) == {"id": FIRST.token, "alt": "0"}


def test_get_video_url_does_not_retry_unknown_episodes(fake_site, sleeps):
    missing = BLACK_CLOVER.episodes[50]

    with pytest.raises(FetchError) as info:
        run(fake_site, lambda c: c.get_video_url(BLACK_CLOVER, missing))
    assert info.value.status == 401
    assert len(fake_site.requests) == 1


def test_download_resumes_after_a_dropped_connection(fake_site, sleeps, tmp_path):
    fake_site.drop_after[FIRST.token] = 1_200
    dest = tmp_path / "ep1.mp4"
    progress = []

    run(
        fake_site,
        lambda c: c.download(
            f"https://cdn.test/DDL/{FIRST.token}.mp4", dest, lambda *p: progress.append(p)
        ),
    )

    assert dest.read_bytes() == video_bytes(1)
    assert not (tmp_path / "ep1.mp4.part").exists()
    assert fake_site.requests[-1].headers["Range"] == "bytes=1200-"
    assert progress[-1] == (5_000, 5_000)
    assert sleeps == [2.0]


def test_download_continues_a_part_file_left_by_a_previous_run(fake_site, tmp_path):
    (tmp_path / "ep1.mp4.part").write_bytes(video_bytes(1)[:3_000])

    run(
        fake_site,
        lambda c: c.download(f"https://cdn.test/DDL/{FIRST.token}.mp4", tmp_path / "ep1.mp4"),
    )

    assert (tmp_path / "ep1.mp4").read_bytes() == video_bytes(1)
    assert fake_site.requests[-1].headers["Range"] == "bytes=3000-"


def test_download_finishes_a_part_file_that_is_already_complete(fake_site, tmp_path):
    (tmp_path / "ep1.mp4.part").write_bytes(video_bytes(1))

    run(
        fake_site,
        lambda c: c.download(f"https://cdn.test/DDL/{FIRST.token}.mp4", tmp_path / "ep1.mp4"),
    )

    assert (tmp_path / "ep1.mp4").read_bytes() == video_bytes(1)


def test_download_starts_over_when_the_server_ignores_the_range(tmp_path):
    data = b"fresh video bytes"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=data))
    (tmp_path / "ep.mp4.part").write_bytes(b"stale")

    async def go():
        async with AnimeWorld(transport=transport) as client:
            await client.download("https://cdn.test/ep.mp4", tmp_path / "ep.mp4")

    asyncio.run(go())
    assert (tmp_path / "ep.mp4").read_bytes() == data


def test_gives_up_on_server_errors_after_max_retries(sleeps):
    transport = httpx.MockTransport(lambda request: httpx.Response(503))

    async def go():
        async with AnimeWorld(retries=3, transport=transport) as client:
            await client.get_anime(f"https://{ANIME_HOST}/play/black-clover-ita.IDsmb")

    with pytest.raises(FetchError, match="after 3 attempts") as info:
        asyncio.run(go())
    assert info.value.status == 503
    assert sleeps == [2.0, 4.0]


def test_requires_context_manager():
    with pytest.raises(RuntimeError, match="context manager"):
        asyncio.run(AnimeWorld().get_video_url(BLACK_CLOVER, FIRST))
