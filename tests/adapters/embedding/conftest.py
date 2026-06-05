"""Embedding adapter test fixtures."""

from __future__ import annotations

import pytest

from core.interfaces.embedder import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """Test double returning fixed non-zero vectors without loading a real model."""

    def __init__(self, dimension: int = 512) -> None:
        self._dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        base = [0.0] * self._dimension
        base[0] = 1.0
        return [base.copy() for _ in texts]

    def dimension(self) -> int:
        return self._dimension


@pytest.fixture
def mock_embedder() -> MockEmbeddingProvider:
    """Return a 512-dimensional mock embedder."""
    return MockEmbeddingProvider(dimension=512)
