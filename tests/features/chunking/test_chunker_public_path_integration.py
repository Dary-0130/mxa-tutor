from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from loguru import logger

from app.config import AppSettings
from core.domain.file_paths import contains_server_path_hint, is_public_file_path
from core.domain.m_file import MFile, MFunction
from core.domain.mat_metadata import MatMetadata, MatVariable
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.project_graph import ProjectGraph
from core.domain.slx_model import SlxBlock, SlxModel
from core.interfaces.vector_store import ChunkRecord, QueryHit
from features.chat._vector_retriever import VectorRetriever
from features.chunking import _project_chunker

_NOW = datetime(2026, 6, 14, 0, 0, 0)
_GRAPH = ProjectGraph("p-public", [], [], [], [], [], [], [])


class FakeEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0]]

    def dimension(self) -> int:
        return 2


class FakeVectorStore:
    def __init__(self, chunks: list[ChunkRecord]) -> None:
        self._chunks = chunks

    async def query(
        self,
        query_embedding: list[float],
        project_id: str,
        top_k: int = 8,
        min_score: float = 0.3,
    ) -> list[QueryHit]:
        _ = query_embedding, project_id, top_k, min_score
        return [QueryHit(chunk, 0.9) for chunk in self._chunks]


def _server_path(project_id: str, relative_path: str) -> str:
    windows_relative = relative_path.replace("/", "\\")
    return rf"D:\mxa-workspace\uploads\{project_id}\{windows_relative}"


def _project() -> Project:
    project_id = "p-public"
    func = MFunction("controller", ["u"], ["y"], (10, 20), "控制器函数")
    block = SlxBlock("b1", "SpeedController", "Gain", {"K": "1"}, (0, 0, 10, 10), "Loop")
    return Project(
        project_id,
        "public.zip",
        ProjectType.GENERAL,
        [
            FileInfo("scripts/main.m", ".m", 10, "主入口文件"),
            FileInfo("models/model.slx", ".slx", 10),
            FileInfo("data/gains.mat", ".mat", 10),
            FileInfo("src/controller.c", ".c", 42),
            FileInfo("include/controller.h", ".h", 58),
        ],
        [
            SlxModel(
                _server_path(project_id, "models/model.slx"),
                "model",
                [block],
                [],
                {"Loop": ["b1"]},
                {},
                [],
            )
        ],
        [
            MFile(
                _server_path(project_id, "scripts/main.m"),
                "script",
                [func],
                [],
                [],
                "function y = controller(u)\ny = u;\nend",
            ),
        ],
        [
            MatMetadata(
                _server_path(project_id, "data/gains.mat"),
                10,
                [MatVariable("Kp", "double", (1, 1), "gain", [])],
            )
        ],
        _NOW,
        {},
    )


def _settings_with_c_h_sources(
    project: Project, chunk_settings: AppSettings, tmp_path
) -> AppSettings:
    upload_root = tmp_path / "uploads"
    project_root = upload_root / project.id
    for folder in ("src", "include"):
        (project_root / folder).mkdir(parents=True)
    (project_root / "src" / "controller.c").write_text(
        "static void controller(void) {\n    Phase = 90;\n}\n",
        encoding="utf-8",
    )
    (project_root / "include" / "controller.h").write_text(
        "typedef struct { float Kp; } PID;\nvoid pid_calc(PID *v);\n",
        encoding="utf-8",
    )
    return chunk_settings.model_copy(update={"upload_dir": str(upload_root)})


def test_chunker_sanitizes_all_file_chunk_paths_and_preserves_line_ranges(
    chunk_settings: AppSettings,
    tmp_path,
) -> None:
    project = _project()
    settings = _settings_with_c_h_sources(project, chunk_settings, tmp_path)

    records = []
    sink_id = logger.add(lambda message: records.append(message.record), level="WARNING")
    try:
        drafts = _project_chunker.build_drafts(project, _GRAPH, settings)
    finally:
        logger.remove(sink_id)

    assert {draft.source_type for draft in drafts} == {
        "c_file",
        "h_file",
        "m_file",
        "m_function",
        "mat_variable",
        "slx_block",
        "slx_subsystem",
    }
    assert all(is_public_file_path(draft.file_path) for draft in drafts)
    assert all(not contains_server_path_hint(draft.file_path) for draft in drafts)
    assert all("\\" not in draft.file_path for draft in drafts)
    assert all("mxa-workspace" not in draft.source_text.lower() for draft in drafts)
    assert all("mxa-workspace" not in draft.chunk_id.lower() for draft in drafts)

    m_function = next(draft for draft in drafts if draft.source_type == "m_function")
    assert m_function.file_path == "scripts/main.m"
    assert m_function.line_range == (10, 20)
    assert "scripts/main.m" in m_function.source_text

    c_h_ranges = [draft.line_range for draft in drafts if draft.source_type in {"c_file", "h_file"}]
    assert c_h_ranges
    assert all(line_range is not None for line_range in c_h_ranges)
    assert all(
        start > 0 and start <= end
        for line_range in c_h_ranges
        if line_range is not None
        for start, end in [line_range]
    )

    none_line_types = {"m_file", "mat_variable", "slx_block", "slx_subsystem"}
    assert all(draft.line_range is None for draft in drafts if draft.source_type in none_line_types)
    assert not [
        record for record in records if record["message"] == "chunk_skipped_public_path_unresolved"
    ]


async def test_public_chunks_flow_through_real_vector_retriever_mapping(
    chunk_settings: AppSettings,
    tmp_path,
) -> None:
    project = _project()
    settings = _settings_with_c_h_sources(project, chunk_settings, tmp_path)
    drafts = _project_chunker.build_drafts(project, _GRAPH, settings)
    chunks = [
        ChunkRecord(**asdict(draft), embedding=[1.0, 0.0], model_name="fake", created_at=_NOW)
        for draft in drafts
    ]

    hits = await VectorRetriever(FakeEmbedder(), FakeVectorStore(chunks)).search(
        project,
        "速度控制器",
    )

    assert hits
    assert all(is_public_file_path(hit.source_ref.file_path) for hit in hits)
    assert all(not contains_server_path_hint(hit.source_ref.file_path) for hit in hits)
    assert any(hit.source_ref.line_range == (10, 20) for hit in hits)
