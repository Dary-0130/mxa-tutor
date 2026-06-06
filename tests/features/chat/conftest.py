from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedder
from adapters.storage._connection import open_connection
from adapters.storage.schema import init_schema
from adapters.storage.sqlite_project_store import SqliteProjectStore
from adapters.storage.sqlite_vector_store import SqliteVectorStore
from app.config import AppSettings
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.slx_model import SlxBlock, SlxModel
from features.chunking import ChunkingService
from features.overview.project_graph_builder import ProjectGraphBuilder


@dataclass
class VectorRagBundle:
    project: Project
    embedder: SentenceTransformerEmbedder
    vector_store: SqliteVectorStore


@pytest.fixture
def vector_rag_settings(monkeypatch: pytest.MonkeyPatch) -> AppSettings:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    return AppSettings(vector_min_score=-1.0)


@pytest.fixture
def vector_rag_project() -> Project:
    return Project(
        id="rag-p1",
        name="speed-loop-demo.zip",
        project_type=ProjectType.MOTOR_CONTROL,
        files=[
            FileInfo("models/speed_loop.slx", ".slx", 2048, "电机速度闭环控制模型"),
        ],
        slx_models=[
            SlxModel(
                file_path="models/speed_loop.slx",
                name="speed_loop",
                blocks=[
                    SlxBlock(
                        block_id="1",
                        name="SpeedController",
                        block_type="PID Controller",
                        parameters={"Kp": "1.2", "Ki": "0.05"},
                        position=(10, 10, 120, 60),
                        parent_subsystem="SpeedLoop",
                    ),
                    SlxBlock(
                        block_id="2",
                        name="MotorPlant",
                        block_type="TransferFcn",
                        parameters={"Numerator": "[1]", "Denominator": "[1 10]"},
                        position=(160, 10, 260, 60),
                        parent_subsystem="SpeedLoop",
                    ),
                ],
                lines=[],
                subsystems={"SpeedLoop": ["1", "2"]},
                solver_config={},
                parse_warnings=[],
            )
        ],
        m_files=[],
        mat_files=[],
        created_at=datetime(2026, 6, 7, 0, 0, 0),
        file_dependencies={},
    )


@pytest.fixture
async def real_project_without_chunks(
    tmp_path: Path,
    vector_rag_project: Project,
) -> VectorRagBundle:
    db_path = str(tmp_path / "mxa.db")
    async with open_connection(db_path) as conn:
        await init_schema(conn)
    project_store = SqliteProjectStore(db_path)
    await project_store.create_pending(vector_rag_project.id, vector_rag_project.name)
    await project_store.mark_ready(vector_rag_project.id, vector_rag_project)
    return VectorRagBundle(
        project=vector_rag_project,
        embedder=SentenceTransformerEmbedder(),
        vector_store=SqliteVectorStore(db_path),
    )


@pytest.fixture
async def real_project_with_chunks(
    tmp_path: Path,
    vector_rag_project: Project,
    vector_rag_settings: AppSettings,
) -> VectorRagBundle:
    db_path = str(tmp_path / "mxa.db")
    async with open_connection(db_path) as conn:
        await init_schema(conn)
    project_store = SqliteProjectStore(db_path)
    await project_store.create_pending(vector_rag_project.id, vector_rag_project.name)
    await project_store.mark_ready(vector_rag_project.id, vector_rag_project)
    embedder = SentenceTransformerEmbedder()
    vector_store = SqliteVectorStore(db_path)
    chunking = ChunkingService(
        embedder=embedder,
        vector_store=vector_store,
        graph_provider=ProjectGraphBuilder(),
        settings=vector_rag_settings,
    )
    added = await chunking.build_embed_store_project_chunks(vector_rag_project)
    assert added > 0
    return VectorRagBundle(
        project=vector_rag_project,
        embedder=embedder,
        vector_store=vector_store,
    )
