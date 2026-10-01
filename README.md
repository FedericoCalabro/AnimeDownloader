# AnimeDownloader

Download whole seasons from [AnimeWorld](https://www.animeworld.ac), several episodes at a time.
Downloads resume where they stopped, whether you pressed Ctrl-C, lost your connection or the
server dropped you.

> **Backstory:** the first version (October 2023) was a small threaded script. It scraped one
> episode's download link and guessed the others by swapping the episode number in it. That
> stopped working once the site spread long series across several file servers. This is a
> complete rewrite as a proper, tested Python package that asks the site for every episode's link.

## Quickstart

You only need [uv](https://docs.astral.sh/uv/getting-started/installation/). It downloads the
right Python version (pinned in `.python-version`) and every dependency for you.

```bash
uv tool install git+https://github.com/FedericoCalabro/AnimeDownloader
anime-downloader
```

With no arguments it asks for everything:

```text
$ anime-downloader
AnimeWorld link: https://www.animeworld.ac/play/black-clover-ita.IDsmb
Black Clover (ITA): 120 episode(s), 1 to 120
Download from episode [1]: 1
Up to episode [120]: 12
Parallel downloads [3]: 4
12 episode(s), 4 at a time → downloads/Black Clover (ITA)
Start downloading? [Y/n]:
  Episodes ━━━━━━━━━━━━━━━━━━╺━━━━━━━━━━━━━━━━━━━━━  5/12 0:04:12
    Episode 6  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  251.0/313.9 MB 1.1 MB/s 0:00:57
    Episode 7  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  156.3/311.4 MB 1.0 MB/s 0:02:35
    Episode 8  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   35.1/312.7 MB 1.1 MB/s 0:04:24
    Episode 9  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    8.4/310.6 MB 1.0 MB/s 0:05:02
```

Paste the link of the anime's page, or of any of its episodes. Old domains such as
`animeworld.so` or `animeworld.tv` work too.

To update later, run `uv tool upgrade anime-downloader`. To try it without installing anything:
`uvx --from git+https://github.com/FedericoCalabro/AnimeDownloader anime-downloader`.

## Usage

```text
anime-downloader [URL] [OPTIONS]
```

| Option              | Description                                                              |
| ------------------- | ------------------------------------------------------------------------ |
| `-f, --from N`      | First episode to download (default: the first)                           |
| `-t, --to N`        | Last episode to download (default: the last)                             |
| `-j, --jobs N`      | Episodes downloaded at the same time, 1 to 16 (default 3)                |
| `-o, --out DIR`     | Download directory, one folder per anime (default `downloads`)           |
| `-y, --yes`         | Never prompt: without `--from`/`--to`, download every episode            |
| `-v, --verbose`     | Debug logging (retries etc.)                                             |
| `--version`         | Show the version and exit                                                |

Anything you leave out is asked for when you run it in a terminal. Pass everything on the command
line, plus `--yes`, to skip the questions, e.g. in a script:

```bash
anime-downloader https://www.animeworld.ac/play/black-clover-ita.IDsmb -f 1 -t 12 -j 4 --yes
```

The file servers limit the speed of each download (about 1 MB/s in October 2026), so parallel
downloads make a big difference: as a rule of thumb, each one needs about 8 Mbit/s of your
connection. Pick the number at the prompt or with `-j`.

### Resuming

Each episode downloads to `<name>.mp4.part` and is renamed to `<name>.mp4` only once complete.
That means you can always run the same command again:

- finished episodes are skipped,
- half-downloaded ones continue from the byte where they stopped,
- dropped connections are retried (with back-off) and resumed automatically during a run.

If some episodes still fail, the command lists them and exits with status 1.

### Output layout

```text
downloads/
└── Black Clover (ITA)/
    ├── BlackClover_Ep_01_ITA.mp4
    ├── BlackClover_Ep_02_ITA.mp4
    └── BlackClover_Ep_03_ITA.mp4.part     # still downloading
```

File names come from the site's servers, so they always include the episode number.

## How it works

1. **Anime page.** The page lists every episode with an opaque token, e.g.
   `<a data-id="sXD8jR" data-episode-num="1">`, all of them in the HTML, even the ones hidden
   behind the "1 - 50 / 51 - 100 / …" tabs. It is parsed with
   [selectolax](https://github.com/rushter/selectolax).
2. **Episode links.** For each selected episode, `/api/episode/info?id=<token>` returns the direct
   `.mp4` link. Episodes of the same anime can live on different servers (One Piece's episode 1
   and episode 732 do), so each one is looked up separately.
3. **Downloads.** [httpx](https://www.python-httpx.org/) streams each file to disk with a few in
   parallel. On a retry or a later run it sends a `Range` request to continue from the bytes
   already on disk. [Rich](https://github.com/Textualize/rich) draws the progress bars.

## Development

```bash
uv sync                 # installs runtime + dev dependencies into .venv
uv run anime-downloader # run from the checkout
uv run pytest           # offline test suite (no network needed)
uv run ruff check .     # lint
uv run ruff format .    # format
```

```text
src/anime_downloader/
├── cli.py         # Typer command, prompts, progress bars
├── downloader.py  # downloads a batch of episodes, a few at a time
├── client.py      # httpx client: anime pages, episode API, resumable downloads, retries
├── parsers.py     # pure URL / HTML / JSON → data functions
└── models.py      # Anime / Episode dataclasses
tests/
├── fixtures/      # real pages saved from the site (scripts and styles removed)
└── test_*.py
```

The tests run against a fake AnimeWorld (`httpx.MockTransport`) that serves the saved pages, the
episode API and a video server that honours `Range` requests and can drop connections halfway
through. If the site changes its markup, save fresh copies of the fixture pages. The failing
tests then show which selectors need updating in `parsers.py`.

## Disclaimer

This is an unofficial, personal project, not affiliated with or endorsed by AnimeWorld. Respect
the site's terms of use and the copyright laws of your country, and don't redistribute what you
download.
