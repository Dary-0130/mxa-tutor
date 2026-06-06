from __future__ import annotations

import os

import pytest

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedder
from adapters.storage.sqlite_project_store import SqliteProjectStore
from adapters.storage.sqlite_vector_store import SqliteVectorStore
from core.interfaces.vector_store import ChunkRecord

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.environ.get("RUN_EMBEDDING_INTEGRATION") != "1",
    reason="set RUN_EMBEDDING_INTEGRATION=1 to load the real embedding model",
)
async def test_real_embedder_round_trips_through_sqlite_vector_store(
    initialized_db_path: str,
    project_store: SqliteProjectStore,
) -> None:
    embedder = SentenceTransformerEmbedder()
    vector_store = SqliteVectorStore(initialized_db_path)
    await project_store.create_pending("p1", "demo.zip")

    texts = [
        "PID controller with proportional and integral gain",
        "Simulink subsystem for a motor speed loop",
    ]
    vectors = embedder.embed(texts)
    await vector_store.add_chunks(
        [
            ChunkRecord(
                chunk_id=f"chunk-{index}",
                project_id="p1",
                source_type="teaching_unit",
                file_path="overview.md",
                symbol_name=None,
                line_range=None,
                block_id=None,
                block_name=None,
                block_type=None,
                parent_subsystem=None,
                source_text=text,
                embedding=vector,
                model_name="BAAI/bge-small-zh-v1.5",
            )
            for index, (text, vector) in enumerate(zip(texts, vectors, strict=True), start=1)
        ]
    )

    query_embedding = embedder.embed(["How does the PID controller set gain?"])[0]
    hits = await vector_store.query(query_embedding, "p1", top_k=2, min_score=-1.0)

    assert hits
    assert hits[0].chunk.source_text in texts
    assert -1.0 <= hits[0].score <= 1.0
