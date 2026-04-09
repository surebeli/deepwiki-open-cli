from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


MetadataValue = str | int | float | bool


@dataclass
class VectorDocument:
    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, MetadataValue]


@dataclass
class QueryResult:
    id: str
    text: str
    metadata: dict[str, MetadataValue]
    relevance_score: float


class BaseVectorStore(ABC):
    @abstractmethod
    def add_documents(self, documents: list[VectorDocument]) -> None:
        ...

    @abstractmethod
    def query(self, embedding: list[float], top_k: int = 20) -> list[QueryResult]:
        ...

    @abstractmethod
    def persist(self) -> None:
        ...

    @abstractmethod
    def load(self, path: str) -> bool:
        ...

    @abstractmethod
    def count(self) -> int:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...


class ChromaVectorStore(BaseVectorStore):
    def __init__(self, persist_path: str, collection_name: str = "chunks"):
        self.persist_path = Path(persist_path)
        self.collection_name = collection_name
        self.persist_path.mkdir(parents=True, exist_ok=True)

        from chromadb import PersistentClient

        self.client = PersistentClient(path=str(self.persist_path))
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def add_documents(self, documents: list[VectorDocument]) -> None:
        if not documents:
            return
        self.collection.add(
            ids=[doc.id for doc in documents],
            documents=[doc.text for doc in documents],
            embeddings=[doc.embedding for doc in documents],
            metadatas=[self._normalize_metadata(doc.metadata) for doc in documents],
        )

    def query(self, embedding: list[float], top_k: int = 20) -> list[QueryResult]:
        if top_k <= 0:
            return []

        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        query_results: list[QueryResult] = []
        for idx, doc_id in enumerate(ids):
            doc_text = documents[idx] if idx < len(documents) else ""
            metadata = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
            distance = float(distances[idx]) if idx < len(distances) and distances[idx] is not None else 1.0
            query_results.append(
                QueryResult(
                    id=doc_id,
                    text=doc_text,
                    metadata=self._normalize_metadata(metadata),
                    relevance_score=max(0.0, 1.0 - distance),
                )
            )
        return query_results

    def persist(self) -> None:
        persist_method = getattr(self.client, "persist", None)
        if callable(persist_method):
            persist_method()

    def load(self, path: str) -> bool:
        new_path = Path(path)
        if not new_path.exists() or not new_path.is_dir():
            return False

        from chromadb import PersistentClient

        self.persist_path = new_path
        self.client = PersistentClient(path=str(self.persist_path))
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except Exception:
            return False
        return self.count() > 0

    def count(self) -> int:
        return int(self.collection.count())

    def clear(self) -> None:
        try:
            self.client.delete_collection(name=self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    @staticmethod
    def _normalize_metadata(metadata: dict[str, object]) -> dict[str, MetadataValue]:
        normalized: dict[str, MetadataValue] = {}
        for key, value in metadata.items():
            if isinstance(value, bool):
                normalized[key] = value
            elif isinstance(value, (str, int, float)):
                normalized[key] = value
            else:
                normalized[key] = str(value)
        return normalized
