"""SentenceTransformerEmbedder unit tests with model loading mocked."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from adapters.embedding.sentence_transformer import (
    DEFAULT_DEVICE,
    DEFAULT_MODEL_NAME,
    DEFAULT_NORMALIZE,
    SentenceTransformerEmbedder,
)


@pytest.fixture
def mock_st_class(mocker):
    """Patch SentenceTransformer to avoid downloading a real model."""
    mock_class = mocker.patch("adapters.embedding.sentence_transformer.SentenceTransformer")
    mock_instance = MagicMock()
    mock_instance.get_sentence_embedding_dimension.return_value = 512
    mock_instance.encode.return_value = np.array([[0.1, 0.2, 0.3]])
    mock_class.return_value = mock_instance
    return mock_class, mock_instance


def test_init_with_defaults_loads_model(mock_st_class):
    mock_class, _ = mock_st_class
    embedder = SentenceTransformerEmbedder()

    mock_class.assert_called_once_with(DEFAULT_MODEL_NAME, device=DEFAULT_DEVICE)
    assert embedder.dimension() == 512


def test_init_with_custom_model_name(mock_st_class):
    mock_class, _ = mock_st_class

    SentenceTransformerEmbedder(model_name="custom/model", device="cuda")

    mock_class.assert_called_once_with("custom/model", device="cuda")


def test_init_empty_model_name_raises(mock_st_class):
    with pytest.raises(ValueError, match="model_name must be non-empty"):
        SentenceTransformerEmbedder(model_name="")


def test_init_whitespace_model_name_raises(mock_st_class):
    with pytest.raises(ValueError, match="model_name must be non-empty"):
        SentenceTransformerEmbedder(model_name="   ")


def test_init_dimension_none_raises(mock_st_class):
    _, mock_instance = mock_st_class
    mock_instance.get_sentence_embedding_dimension.return_value = None

    with pytest.raises(ValueError, match="model dimension is unavailable"):
        SentenceTransformerEmbedder()


def test_embed_returns_list_of_lists(mock_st_class):
    _, mock_instance = mock_st_class
    mock_instance.encode.return_value = np.array([[1.0, 2.0], [3.0, 4.0]])
    embedder = SentenceTransformerEmbedder()

    result = embedder.embed(["text1", "text2"])

    assert isinstance(result, list)
    assert all(isinstance(vector, list) for vector in result)
    assert result == [[1.0, 2.0], [3.0, 4.0]]


def test_embed_empty_input_returns_empty(mock_st_class):
    _, mock_instance = mock_st_class
    embedder = SentenceTransformerEmbedder()

    assert embedder.embed([]) == []
    mock_instance.encode.assert_not_called()


def test_embed_passes_normalize_flag(mock_st_class):
    _, mock_instance = mock_st_class
    mock_instance.encode.return_value = np.array([[1.0]])
    embedder = SentenceTransformerEmbedder(normalize=False)

    embedder.embed(["text"])

    call_kwargs = mock_instance.encode.call_args.kwargs
    assert call_kwargs["normalize_embeddings"] is False


def test_dimension_returns_loaded_dimension(mock_st_class):
    _, mock_instance = mock_st_class
    mock_instance.get_sentence_embedding_dimension.return_value = 768

    embedder = SentenceTransformerEmbedder()

    assert embedder.dimension() == 768


def test_default_normalize_is_true():
    assert DEFAULT_NORMALIZE is True


def test_default_model_is_bge_small_zh():
    assert DEFAULT_MODEL_NAME == "BAAI/bge-small-zh-v1.5"


def test_default_device_is_cpu():
    assert DEFAULT_DEVICE == "cpu"
