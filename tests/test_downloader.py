import asyncio

from conftest import BLACK_CLOVER, video_bytes

from anime_downloader.downloader import download_episodes


def test_download_episodes_skips_finished_files_and_collects_failures(fake_site, tmp_path):
    first, second, third, fourth = BLACK_CLOVER.episodes[:4]
    (tmp_path / f"{second.token}.mp4").write_bytes(b"downloaded last time")
    done = []

    async def go():
        async with fake_site.client(retries=1) as site:
            return await download_episodes(
                site,
                BLACK_CLOVER,
                [first, second, third, fourth],
                tmp_path,
                jobs=2,
                on_done=done.append,
            )

    report = asyncio.run(go())

    assert report.downloaded == [tmp_path / f"{first.token}.mp4", tmp_path / f"{third.token}.mp4"]
    assert report.skipped == [tmp_path / f"{second.token}.mp4"]
    assert [episode for episode, _ in report.failed] == [fourth]
    assert (tmp_path / f"{third.token}.mp4").read_bytes() == video_bytes(3)
    assert (tmp_path / f"{second.token}.mp4").read_bytes() == b"downloaded last time"
    assert sorted(done, key=lambda ep: int(ep.number)) == [first, second, third, fourth]
