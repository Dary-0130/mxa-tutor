"""SentenceTransformerEmbedder integration tests for the real model.

Set ``RUN_EMBEDDING_INTEGRATION=1`` to opt in. CI leaves this unset, so these
tests are skipped by default and do not download the model.
"""

from __future__ import annotations

import os

import pytest

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedder

RUN_INTEGRATION = os.getenv("RUN_EMBEDDING_INTEGRATION") == "1"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(
        not RUN_INTEGRATION,
        reason="Set RUN_EMBEDDING_INTEGRATION=1 to run real embedding model tests.",
    ),
]


def test_real_model_load_and_embed() -> None:
    """Load bge-small-zh-v1.5 and verify its dimension contract."""
    embedder = SentenceTransformerEmbedder()

    assert embedder.dimension() == 512, (
        f"bge-small-zh-v1.5 contract dimension is 512, got {embedder.dimension()}. "
        "If the default model changed, sync MockEmbeddingProvider, 02 decision 2, "
        "and downstream vector storage assumptions."
    )

    vectors = embedder.embed(["你好,这是测试文本", "Hello world"])
    assert len(vectors) == 2
    assert all(len(vector) == embedder.dimension() for vector in vectors)
    assert all(isinstance(value, float) for vector in vectors for value in vector)


def test_real_model_embed_empty_input() -> None:
    """Empty input returns an empty list without calling encode."""
    embedder = SentenceTransformerEmbedder()
    assert embedder.embed([]) == []
