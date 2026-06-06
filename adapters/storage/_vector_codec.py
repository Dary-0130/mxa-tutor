"""Little-endian float32 vector BLOB codec."""

from __future__ import annotations

import numpy as np

from core.domain.exceptions import VectorStoreError

_FLOAT32_LE = np.dtype("<f4")


def encode_vector(vec: list[float]) -> bytes:
    """Encode a one-dimensional vector as little-endian float32 bytes."""

    try:
        arr = np.asarray(vec, dtype=_FLOAT32_LE)
    except (TypeError, ValueError):
        raise VectorStoreError("vector_encode_failed") from None

    if arr.ndim != 1:
        raise VectorStoreError("vector_encode_failed")
    if arr.size == 0:
        raise VectorStoreError("empty_embedding")
    return np.ascontiguousarray(arr, dtype=_FLOAT32_LE).tobytes(order="C")


def decode_vector(blob: bytes, expected_dim: int) -> list[float]:
    """Decode little-endian float32 bytes and validate the expected dimension."""

    if expected_dim <= 0 or len(blob) % _FLOAT32_LE.itemsize != 0:
        raise VectorStoreError("blob_length_mismatch")
    if len(blob) // _FLOAT32_LE.itemsize != expected_dim:
        raise VectorStoreError("blob_length_mismatch")

    try:
        arr = np.frombuffer(blob, dtype=_FLOAT32_LE)
    except (TypeError, ValueError):
        raise VectorStoreError("vector_decode_failed") from None
    return arr.tolist()
