from __future__ import annotations

from pathlib import Path

from deepwiki.data.vector_store import ChromaVectorStore, VectorDocument


class _FakeCollection:
    def __init__(self) -> None:
        self.add_called = False

    def add(self, **kwargs) -> None:
        self.add_called = True
        self.kwargs = kwargs

    def query(self, **kwargs):
        return {
            "ids": [["1"]],
            "documents": [["body"]],
            "metadatas": [[{"file_path": "a.py", "chunk_index": 1}]],
            "distances": [[0.2]],
        }

    def count(self) -> int:
        return 1


def test_vector_store_add_and_query_without_chromadb_init() -> None:
    store = ChromaVectorStore.__new__(ChromaVectorStore)
    store.collection = _FakeCollection()

    store.add_documents(
        [VectorDocument(id="1", text="body", embedding=[0.1], metadata={"k": "v", "obj": {"x": 1}})]
    )
    assert store.collection.add_called is True

    results = store.query([0.1], top_k=1)
    assert len(results) == 1
    assert results[0].id == "1"
    assert results[0].relevance_score == 0.8


def test_vector_store_query_top_k_le_zero() -> None:
    store = ChromaVectorStore.__new__(ChromaVectorStore)
    store.collection = _FakeCollection()
    assert store.query([0.1], top_k=0) == []


def test_vector_store_query_handles_missing_fields() -> None:
    class _PartialCollection:
        def query(self, **kwargs):
            return {"ids": [["1", "2"]], "documents": [["only-one"]], "metadatas": [[None]], "distances": [[None]]}

    store = ChromaVectorStore.__new__(ChromaVectorStore)
    store.collection = _PartialCollection()
    results = store.query([0.3], top_k=2)
    assert len(results) == 2
    assert results[0].text == "only-one"
    assert results[0].metadata == {}
    assert results[0].relevance_score == 0.0
    assert results[1].text == ""
    assert results[1].metadata == {}


def test_vector_store_persist_load_and_clear(tmp_path: Path) -> None:
    class _Client:
        def __init__(self) -> None:
            self.persist_called = False
            self.deleted = False
            self.raise_on_get = False

        def persist(self) -> None:
            self.persist_called = True

        def delete_collection(self, name: str) -> None:
            self.deleted = True
            raise RuntimeError("ignore")

        def get_or_create_collection(self, name: str):
            return _FakeCollection()

        def get_collection(self, name: str):
            if self.raise_on_get:
                raise RuntimeError("not found")
            return _FakeCollection()

    store = ChromaVectorStore.__new__(ChromaVectorStore)
    store.collection_name = "chunks"
    store.client = _Client()
    store.collection = _FakeCollection()
    store.persist()
    assert store.client.persist_called is True

    store.clear()
    assert store.client.deleted is True
    assert isinstance(store.collection, _FakeCollection)


def test_vector_store_load_branches(monkeypatch, tmp_path: Path) -> None:
    store = ChromaVectorStore.__new__(ChromaVectorStore)
    store.collection_name = "chunks"

    assert store.load(str(tmp_path / "missing")) is False

    class _ClientRaise:
        def __init__(self, path: str) -> None:
            self.path = path

        def get_collection(self, name: str):
            raise RuntimeError("no collection")

    import deepwiki.data.vector_store as vector_store_module

    monkeypatch.setattr(vector_store_module, "Path", Path)
    monkeypatch.setitem(__import__("sys").modules, "chromadb", type("M", (), {"PersistentClient": _ClientRaise}))
    (tmp_path / "idx").mkdir()
    assert store.load(str(tmp_path / "idx")) is False


def test_vector_store_normalize_metadata_casts_objects() -> None:
    normalized = ChromaVectorStore._normalize_metadata({"a": "x", "b": 1, "c": True, "d": {"z": 1}})
    assert normalized["a"] == "x"
    assert normalized["b"] == 1
    assert normalized["c"] is True
    assert normalized["d"] == "{'z': 1}"
