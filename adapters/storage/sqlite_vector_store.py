"""SQLite VectorStore implementation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import aiosqlite
import numpy as np
from loguru import logger

from adapters.storage._connection import open_connection
from adapters.storage._vector_codec import _FLOAT32_LE, decode_vector, encode_vector
from core.domain.exceptions import ProjectNotFoundError, VectorStoreError
from core.interfaces.vector_store import ChunkRecord, QueryHit, VectorStore


class SqliteVectorStore(VectorStore):
    """SQLite-backed vector store using one connection per operation."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def aclose(self) -> None:
        """MCS stage opens and closes connections per method."""

    async def add_chunks(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return

        embedding_dim = _batch_embedding_dim(chunks)
        project_ids = {chunk.project_id for chunk in chunks}

        async with open_connection(self._db_path) as conn:
            try:
                await conn.execute("BEGIN")
                for project_id in project_ids:
                    await _ensure_project_exists(conn, project_id)
                    await _ensure_project_dim_matches(conn, project_id, embedding_dim)

                rows = [_insert_row(chunk, embedding_dim) for chunk in chunks]
                await conn.executemany(
                    "INSERT INTO chunks("
                    "chunk_id, project_id, source_type, file_path, symbol_name, "
                    "line_start, line_end, block_id, block_name, block_type, "
                    "parent_subsystem, source_text, embedding, embedding_dim, "
                    "model_name, created_at"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    rows,
                )
                await conn.commit()
            except ProjectNotFoundError:
                await conn.rollback()
                raise
            except VectorStoreError:
                await conn.rollback()
                raise
            except aiosqlite.IntegrityError:
                await conn.rollback()
                raise ValueError("chunk_id already exists") from None
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteVectorStore.add_chunks failed: chunk_count={} exception={}",
                    len(chunks),
                    type(exc).__name__,
                )
                raise VectorStoreError("sqlite_operation_failed") from None

    async def query(
        self,
        query_embedding: list[float],
        project_id: str,
        top_k: int = 8,
        min_score: float = 0.3,
    ) -> list[QueryHit]:
        _validate_query_args(top_k, min_score)

        rows = await self._fetch_project_chunks(project_id)
        if not rows:
            return []

        embedding_dim = _single_embedding_dim(rows)
        if len(query_embedding) != embedding_dim:
            raise VectorStoreError("query_dim_mismatch")

        vectors = [decode_vector(row["embedding"], embedding_dim) for row in rows]
        scores = _cosine_scores(vectors, query_embedding)

        hits: list[QueryHit] = []
        for row, score in zip(rows, scores, strict=True):
            score_float = float(score)
            if score_float >= min_score:
                hits.append(QueryHit(chunk=_chunk_from_row(row, embedding_dim), score=score_float))

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]

    async def delete_by_project_id(self, project_id: str) -> int:
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "DELETE FROM chunks WHERE project_id=?",
                    (project_id,),
                )
                await conn.commit()
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteVectorStore.delete_by_project_id failed: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise VectorStoreError("sqlite_operation_failed") from None
        return int(cur.rowcount or 0)

    async def get_chunk_count(self, project_id: str) -> int:
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "SELECT COUNT(*) AS count FROM chunks WHERE project_id=?",
                    (project_id,),
                )
                row = await cur.fetchone()
            except aiosqlite.OperationalError as exc:
                logger.error(
                    "SqliteVectorStore.get_chunk_count failed: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise VectorStoreError("sqlite_operation_failed") from None
        if row is None:
            raise VectorStoreError("sqlite_operation_failed")
        return int(row["count"])

    async def _fetch_project_chunks(self, project_id: str) -> list[aiosqlite.Row]:
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "SELECT chunk_id, project_id, source_type, file_path, symbol_name, "
                    "line_start, line_end, block_id, block_name, block_type, "
                    "parent_subsystem, source_text, embedding, embedding_dim, "
                    "model_name, created_at "
                    "FROM chunks WHERE project_id=?",
                    (project_id,),
                )
                rows = await cur.fetchall()
            except aiosqlite.OperationalError as exc:
                logger.error(
                    "SqliteVectorStore.query failed: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise VectorStoreError("sqlite_operation_failed") from None
        return list(rows)


def _batch_embedding_dim(chunks: list[ChunkRecord]) -> int:
    dims = {len(chunk.embedding) for chunk in chunks}
    if len(dims) != 1:
        raise ValueError("mixed_embedding_dim")
    return dims.pop()


async def _ensure_project_exists(conn: aiosqlite.Connection, project_id: str) -> None:
    cur = await conn.execute(
        "SELECT 1 FROM project_status_record WHERE project_id=?",
        (project_id,),
    )
    if await cur.fetchone() is None:
        raise ProjectNotFoundError(f"project not found: {project_id}")


async def _ensure_project_dim_matches(
    conn: aiosqlite.Connection,
    project_id: str,
    embedding_dim: int,
) -> None:
    cur = await conn.execute(
        "SELECT DISTINCT embedding_dim FROM chunks WHERE project_id=?",
        (project_id,),
    )
    dims = {int(row["embedding_dim"]) for row in await cur.fetchall()}
    if len(dims) > 1 or (dims and dims != {embedding_dim}):
        raise VectorStoreError("embedding_dim_mismatch")


def _insert_row(chunk: ChunkRecord, embedding_dim: int) -> tuple[Any, ...]:
    line_start, line_end = _line_bounds(chunk.line_range)
    created_at = chunk.created_at or datetime.utcnow()
    return (
        chunk.chunk_id,
        chunk.project_id,
        chunk.source_type,
        chunk.file_path,
        chunk.symbol_name,
        line_start,
        line_end,
        chunk.block_id,
        chunk.block_name,
        chunk.block_type,
        chunk.parent_subsystem,
        chunk.source_text,
        encode_vector(chunk.embedding),
        embedding_dim,
        chunk.model_name,
        created_at.isoformat(),
    )


def _line_bounds(line_range: tuple[int, int] | None) -> tuple[int | None, int | None]:
    if line_range is None:
        return None, None
    return line_range


def _validate_query_args(top_k: int, min_score: float) -> None:
    if top_k < 1 or top_k > 50:
        raise ValueError("invalid top_k")
    if min_score < -1.0 or min_score > 1.0:
        raise ValueError("invalid min_score")


def _single_embedding_dim(rows: list[aiosqlite.Row]) -> int:
    dims = {int(row["embedding_dim"]) for row in rows}
    if len(dims) != 1:
        raise VectorStoreError("embedding_dim_mismatch")
    return dims.pop()


def _cosine_scores(vectors: list[list[float]], query_embedding: list[float]) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=_FLOAT32_LE)
    query = np.asarray(query_embedding, dtype=_FLOAT32_LE)
    dots = matrix @ query
    denom = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
    return np.divide(dots, denom, out=np.zeros_like(dots), where=denom > 1e-12)


def _chunk_from_row(row: aiosqlite.Row, embedding_dim: int) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=row["chunk_id"],
        project_id=row["project_id"],
        source_type=row["source_type"],
        file_path=row["file_path"],
        symbol_name=row["symbol_name"],
        line_range=_line_range_from_row(row),
        block_id=row["block_id"],
        block_name=row["block_name"],
        block_type=row["block_type"],
        parent_subsystem=row["parent_subsystem"],
        source_text=row["source_text"],
        embedding=decode_vector(row["embedding"], embedding_dim),
        model_name=row["model_name"],
        created_at=_created_at_from_row(row),
    )


def _line_range_from_row(row: aiosqlite.Row) -> tuple[int, int] | None:
    start = row["line_start"]
    end = row["line_end"]
    if start is None and end is None:
        return None
    if start is None or end is None:
        raise VectorStoreError("invalid_line_range")
    return int(start), int(end)


def _created_at_from_row(row: aiosqlite.Row) -> datetime:
    try:
        return datetime.fromisoformat(row["created_at"])
    except ValueError:
        raise VectorStoreError("invalid_created_at") from None
