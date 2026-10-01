"""Data models for anime pages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_LEADING_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True, slots=True)
class Episode:
    """One episode as listed on an anime page."""

    number: str
    #: Opaque id the site's episode API expects, e.g. ``SuNI0S``.
    token: str

    @property
    def value(self) -> float | None:
        """Numeric value of ``number`` (``"12.5"`` → 12.5), or ``None`` if it has none."""
        match = _LEADING_NUMBER.match(self.number)
        return float(match[0]) if match else None


@dataclass(frozen=True, slots=True)
class Anime:
    """An anime page on AnimeWorld and the episodes it lists, in site order."""

    title: str
    url: str
    episodes: tuple[Episode, ...] = field(default_factory=tuple)

    def select(self, first: float | None = None, last: float | None = None) -> list[Episode]:
        """Episodes numbered between ``first`` and ``last`` (both inclusive, both optional)."""
        if first is None and last is None:
            return list(self.episodes)
        low = float("-inf") if first is None else first
        high = float("inf") if last is None else last
        return [ep for ep in self.episodes if ep.value is not None and low <= ep.value <= high]
