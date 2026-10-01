import pytest
from conftest import BLACK_CLOVER, video_bytes
from typer.testing import CliRunner

from anime_downloader import cli

runner = CliRunner()
FOLDER = "Black Clover (ITA)"


@pytest.fixture(autouse=True)
def offline(fake_site, monkeypatch):
    monkeypatch.setattr(cli, "AnimeWorld", fake_site.client)


def output(result) -> str:
    return " ".join(result.output.split())


def test_prompts_for_whatever_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_stdin_is_tty", lambda: True)
    link = "www.animeworld.so/play/black-clover-ita.IDsmb"
    answers = f"not a link\n{link}\n1\n3\n50\n2\n\n"

    result = runner.invoke(cli.app, ["--out", str(tmp_path)], input=answers)

    assert result.exit_code == 0, result.output
    assert "expected a link like" in output(result)
    assert "120 episode(s), 1 to 120" in output(result)
    assert "expected a number from 1 to 16, got '50'" in output(result)
    assert "3 episode(s), 2 at a time" in output(result)
    files = sorted(path.name for path in (tmp_path / FOLDER).iterdir())
    assert files == sorted(f"{ep.token}.mp4" for ep in BLACK_CLOVER.episodes[:3])


def test_runs_without_prompts_and_fails_when_an_episode_fails(tmp_path):
    url = "https://www.animeworld.ac/play/black-clover-ita.IDsmb"

    result = runner.invoke(cli.app, [url, "-f", "3", "-t", "4", "-o", str(tmp_path), "-y"])

    assert result.exit_code == 1
    assert "Failed episode(s): 4" in output(result)
    third = BLACK_CLOVER.episodes[2]
    assert (tmp_path / FOLDER / f"{third.token}.mp4").read_bytes() == video_bytes(3)


def test_requires_a_link_when_not_interactive():
    result = runner.invoke(cli.app, [])

    assert result.exit_code == 2
    assert "required when not running in a terminal" in output(result)


def test_prints_titles_verbatim_even_with_brackets(fake_site, tmp_path):
    fake_site.page = fake_site.page.replace(">Black Clover (ITA)<", ">[witch] Black Clover<")
    url = "https://www.animeworld.ac/play/black-clover-ita.IDsmb"

    result = runner.invoke(cli.app, [url, "-f", "1", "-t", "1", "-o", str(tmp_path), "-y"])

    assert result.exit_code == 0, result.output
    assert "[witch] Black Clover: 120 episode(s)" in output(result)
    assert (tmp_path / "[witch] Black Clover").is_dir()
