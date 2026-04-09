from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class CompletionRequest:
    prompt: str
    model: str
    provider: str
    stream: bool = False


@dataclass
class CompletionResponse:
    content: str
    model: str
    provider: str


@dataclass
class EmbeddingRequest:
    texts: list[str]
    model: str
    provider: str


@dataclass
class EmbeddingResponse:
    embeddings: list[list[float]]
    model: str
    provider: str


class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        ...

    @abstractmethod
    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        ...
