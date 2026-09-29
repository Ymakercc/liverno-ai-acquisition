"""Small search provider contract for Session B1."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderSearchResult:
    title: str
    url: str
    snippet: str
    rank: int
    raw: dict


class SearchProvider(Protocol):
    name: str

    def search(
        self,
        query: str,
        *,
        country_code: str | None,
        language: str | None,
        limit: int,
    ) -> list[ProviderSearchResult]:
        """Run one search query and return normalized organic results."""
