from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    chunk_id: str
    file_path: str
    chunk_index: int
    text: str


def split_text(file_path: str, content: str, chunk_size: int, chunk_overlap: int) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0")

    words = list(re.finditer(r"\S+", content))
    if not words:
        return []

    step = max(1, chunk_size - chunk_overlap)
    chunks: list[TextChunk] = []

    chunk_index = 0
    for start_word in range(0, len(words), step):
        end_word = min(len(words), start_word + chunk_size)
        start_pos = words[start_word].start()
        end_pos = words[end_word - 1].end()
        chunk_text = content[start_pos:end_pos].strip()
        if chunk_text:
            chunks.append(
                TextChunk(
                    chunk_id=f"{file_path}::{chunk_index}",
                    file_path=file_path,
                    chunk_index=chunk_index,
                    text=chunk_text,
                )
            )
            chunk_index += 1
        if end_word == len(words):
            break

    return chunks


def split_documents(
    files: list[tuple[str, str]],
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for file_path, content in files:
        chunks.extend(
            split_text(
                file_path=file_path,
                content=content,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
    return chunks
