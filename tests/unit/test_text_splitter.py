from __future__ import annotations

import pytest

from deepwiki.data.text_splitter import split_text


def test_split_text_basic_overlap() -> None:
    content = "one two three four five six"
    chunks = split_text("a.py", content, chunk_size=3, chunk_overlap=1)

    assert len(chunks) >= 2
    assert chunks[0].chunk_id == "a.py::0"
    assert "one two three" in chunks[0].text
    assert "three" in chunks[1].text


def test_split_text_invalid_args() -> None:
    with pytest.raises(ValueError):
        split_text("a.py", "x y", chunk_size=0, chunk_overlap=0)
    with pytest.raises(ValueError):
        split_text("a.py", "x y", chunk_size=2, chunk_overlap=-1)
