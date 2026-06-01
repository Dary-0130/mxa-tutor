import pytest

from core.interfaces.embedder import EmbeddingProvider


def test_embedding_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        EmbeddingProvider()


class _StubEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(index)] for index, _ in enumerate(texts)]

    def dimension(self) -> int:
        return 1


def test_embedding_provider_stub_works() -> None:
    provider = _StubEmbeddingProvider()

    assert provider.embed(["a", "b"]) == [[0.0], [1.0]]
    assert provider.dimension() == 1
