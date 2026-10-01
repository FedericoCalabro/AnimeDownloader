import pytest
from conftest import ANIME_URL, load_fixture

from anime_downloader.models import Anime, Episode
from anime_downloader.parsers import (
    ParseError,
    anime_page_url,
    parse_anime,
    parse_video_url,
    video_filename,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.animeworld.ac/play/black-clover-ita.IDsmb",
        "https://www.animeworld.ac/play/black-clover-ita.IDsmb/SuNI0S",
        "  www.animeworld.ac/play/black-clover-ita.IDsmb/  ",
    ],
)
def test_anime_page_url_normalises_anime_and_episode_links(url):
    assert anime_page_url(url) == ANIME_URL


def test_anime_page_url_keeps_old_domains_for_the_redirect():
    assert anime_page_url("https://www.animeworld.so/play/one-piece-subita.qzG-LE/HPKmX1") == (
        "https://www.animeworld.so/play/one-piece-subita.qzG-LE"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://www.animeworld.ac/",
        "https://www.animeworld.ac/anime/black-clover-ita.IDsmb",
        "https://www.animeworld.ac/play/black-clover/a/b",
        "ftp://www.animeworld.ac/play/black-clover-ita.IDsmb",
        "black clover",
    ],
)
def test_anime_page_url_rejects_other_links(url):
    with pytest.raises(ParseError):
        anime_page_url(url)


def test_parse_anime_lists_every_episode_across_ranges():
    anime = parse_anime(load_fixture("anime_black-clover-ita.html"), ANIME_URL)

    assert anime.title == "Black Clover (ITA)"
    assert [ep.number for ep in anime.episodes] == [str(n) for n in range(1, 121)]
    assert anime.episodes[0] == Episode(number="1", token="sXD8jR")
    assert anime.episodes[-1] == Episode(number="120", token="SuNI0S")


def test_parse_anime_without_episodes_yet():
    anime = parse_anime(load_fixture("anime_upcoming.html"), ANIME_URL)

    assert anime.title == "Are You a Jirai Girl, Chihara-san?"
    assert anime.episodes == ()


def test_parse_anime_rejects_other_pages():
    with pytest.raises(ParseError):
        parse_anime("<html><body><h1>Not found</h1></body></html>", ANIME_URL)


def test_parse_video_url():
    payload = {"grabber": "https://srv.example/DDL/ANIME/X/X_Ep_01_SUB_ITA.mp4", "name": "abc"}

    assert parse_video_url(payload) == payload["grabber"]


@pytest.mark.parametrize("payload", [{"error": True}, {"grabber": ""}, {"grabber": "/x.mp4"}, []])
def test_parse_video_url_rejects_payloads_without_a_link(payload):
    with pytest.raises(ParseError):
        parse_video_url(payload)


def test_video_filename_decodes_and_sanitises():
    url = "https://srv.example/DDL/ANIME/ReZero/Re%3AZero_Ep_01_SUB_ITA.mp4?token=1"

    assert video_filename(url) == "Re_Zero_Ep_01_SUB_ITA.mp4"


def test_select_episodes_by_number():
    numbers = ["1", "2", "3", "12", "12.5", "Special"]
    anime = Anime("A", ANIME_URL, tuple(Episode(n, f"t{n}") for n in numbers))

    def pick(first, last):
        return [ep.number for ep in anime.select(first, last)]

    assert pick(None, None) == numbers
    assert pick(2, 3) == ["2", "3"]
    assert pick(12, None) == ["12", "12.5"]
    assert pick(None, 1) == ["1"]
    assert pick(20, 30) == []
