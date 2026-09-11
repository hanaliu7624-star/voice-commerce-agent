from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from openai import OpenAI

from voice_commerce.config import (
    EMBEDDING_MODEL,
    INDEX_PATH,
    LLM_BASE_URL,
    POLICY_DIR,
    require_api_key,
)


def _client() -> OpenAI:
    return OpenAI(api_key=require_api_key(), base_url=LLM_BASE_URL)


def _chunk_markdown(document_id: str, text: str) -> list[dict[str, str]]:
    parts = re.split(r"\n(?=## )", text.strip())
    chunks = []
    for i, part in enumerate(parts):
        content = part.strip()
        if not content:
            continue
        chunks.append(
            {
                "document_id": f"{document_id}#{i}",
                "source": document_id,
                "content": content,
            }
        )
    return chunks


def load_policy_chunks() -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        chunks.extend(_chunk_markdown(path.stem, path.read_text(encoding="utf-8")))
    return chunks


def _embed(texts: list[str]) -> list[list[float]]:
    client = _client()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def build_index(index_path: Path | None = None) -> Path:
    path = index_path or INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    chunks = load_policy_chunks()
    vectors = _embed([c["content"] for c in chunks])
    payload = {"chunks": chunks, "vectors": vectors}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _load_index(index_path: Path | None = None) -> tuple[list[dict[str, str]], np.ndarray]:
    path = index_path or INDEX_PATH
    if not path.exists():
        build_index(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["chunks"], np.array(payload["vectors"], dtype=np.float32)


def retrieve(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    chunks, matrix = _load_index()
    query_vec = np.array(_embed([query])[0], dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_vec) + 1e-9
    scores = matrix @ query_vec / norms
    top = np.argsort(scores)[::-1][:top_k]
    results = []
    for idx in top:
        item = dict(chunks[int(idx)])
        item["score"] = round(float(scores[int(idx)]), 4)
        results.append(item)
    return results
