from typing import Protocol

from deepwiki.core.models import WikiResult


class OutputFormatter(Protocol):
    def render(self, result: WikiResult) -> None:
        ...
