from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sys
import zipfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.classifier.general_project_type_resolver import GeneralProjectTypeResolver
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedder
from adapters.llm import DeepSeekTextProvider
from adapters.parser.dependency_analyzer import analyze_dependencies
from adapters.parser.file_classifier import classify_files
from adapters.parser.m_parser import MParserImpl
from adapters.parser.slx_parser import SlxParserImpl
from adapters.parser.zip_extractor import safe_extract
from adapters.storage._connection import open_connection
from adapters.storage.schema import init_schema
from adapters.storage.sqlite_project_store import SqliteProjectStore
from adapters.storage.sqlite_vector_store import SqliteVectorStore
from app.config import AppSettings
from core.domain.exceptions import OverviewGenerationError
from core.domain.project import Project, ProjectType
from features.chunking import ChunkingService
from features.overview import InMemoryOverviewCache
from features.overview.overview_schemas import ProjectOverview
from features.overview.overview_service import ProjectOverviewService
from features.overview.project_graph_builder import ProjectGraphBuilder


AD_HOC_ROOT = ROOT / "eval" / "ad_hoc"
INPUTS_DIR = AD_HOC_ROOT / "inputs"
UPLOADS_DIR = AD_HOC_ROOT / "uploads"
OVERVIEWS_DIR = AD_HOC_ROOT / "overviews"
EVAL_DB_PATH = AD_HOC_ROOT / "eval.sqlite"
PROJECT_MAP_PATH = AD_HOC_ROOT / "project_map_resolved.json"
MANIFEST_PATH = AD_HOC_ROOT / "eval_db_build_manifest.json"

CASES = [
    ("01_ee_a", Path(r"E:\桌面\VSC\DFIG5.slx")),
    ("02_ee_b", Path(r"E:\桌面\VSC\MMC_6M_3Phase.slx")),
    ("03_ee_c", Path(r"E:\桌面\VSC\PMSG25.slx")),
    ("04_ee_d", Path(r"E:\桌面\VSC\VSC.slx")),
]

PROJECT_TYPE_BY_ALIAS = {
    "01_ee_a": "new_energy",
    "02_ee_b": "power_electronics",
    "03_ee_c": "new_energy",
    "04_ee_d": "power_electronics",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_dirs() -> None:
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OVERVIEWS_DIR.mkdir(parents=True, exist_ok=True)


def resolve_source_slx(source: Path) -> Path:
    if source.exists():
        return source
    fallback = AD_HOC_ROOT / source.name
    if fallback.exists():
        return fallback
    raise FileNotFoundError(str(source))


def write_alias_zip(alias: str, source_slx: Path) -> Path:
    zip_path = INPUTS_DIR / f"{alias}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(source_slx, arcname=f"{alias}.slx")
    return zip_path


async def init_eval_db() -> None:
    async with open_connection(str(EVAL_DB_PATH)) as conn:
        await init_schema(conn)


async def ingest_one(
    *,
    alias: str,
    zip_path: Path,
    settings: AppSettings,
    project_store: SqliteProjectStore,
    chunking_service: ChunkingService,
    vector_store: SqliteVectorStore,
) -> dict[str, Any]:
    project_id = str(uuid4())
    await project_store.create_pending(project_id, f"{alias}.zip")
    project_dir = UPLOADS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=False)
    try:
        extracted_root = await asyncio.to_thread(
            safe_extract,
            zip_path.read_bytes(),
            project_dir,
            settings,
        )
        file_infos = classify_files(extracted_root, extracted_root)
        slx_parser = SlxParserImpl()
        m_parser = MParserImpl()

        slx_models = []
        for file_info in file_infos:
            if file_info.file_type == ".slx":
                parsed = slx_parser.parse(str(extracted_root / file_info.relative_path))
                slx_models.append(replace(parsed, file_path=file_info.relative_path))

        m_files = []
        for file_info in file_infos:
            if file_info.file_type == ".m":
                m_files.append(m_parser.parse(str(extracted_root / file_info.relative_path)))

        project = Project(
            id=project_id,
            name=f"{alias}.zip",
            project_type=ProjectType.GENERAL,
            files=file_infos,
            slx_models=slx_models,
            m_files=m_files,
            mat_files=[],
            created_at=datetime.utcnow(),
            file_dependencies=analyze_dependencies(file_infos, m_files, str(extracted_root)),
        )
        await project_store.mark_ready(project_id, project)
        await chunking_service.build_embed_store_project_chunks(project)
        status = await project_store.get_status_view(project_id)
        chunk_count = await vector_store.get_chunk_count(project_id)
        ingest_status = "ready" if status.status == "ready" and chunk_count > 0 else "partial"
        return {
            "runtime_project_id": project_id,
            "status": status.status,
            "error_code": status.error_code,
            "chunk_count": chunk_count,
            "ingest_status": ingest_status,
            "file_count": len(file_infos),
            "slx_count": len(slx_models),
            "m_count": len(m_files),
        }
    except Exception:
        await project_store.mark_failed(project_id, "internal_error")
        shutil.rmtree(project_dir, ignore_errors=True)
        raise


def overview_to_markdown(alias: str, overview: ProjectOverview) -> str:
    lines: list[str] = [
        f"# {alias} Overview",
        "",
        f"- Title: {overview.project_title}",
        f"- Type: {overview.project_type}",
        f"- Summary: {overview.one_sentence_summary}",
        "",
        "## Main Entry Files",
    ]
    for item in overview.main_entry_files:
        lines.append(f"- `{item.file_path}`: {item.role}")
    lines.extend(["", "## Main Simulink Models"])
    for item in overview.main_simulink_models:
        lines.append(f"- `{item.file_path}`: {item.summary}")
    lines.extend(["", "## Execution Flow"])
    for item in overview.main_execution_flow:
        lines.append(f"- {item}")
    lines.extend(["", "## Key Files"])
    for item in overview.key_files:
        lines.append(f"- `{item.file_path}`: {item.why_key}")
    lines.extend(["", "## Key Blocks"])
    for item in overview.key_blocks:
        lines.append(
            f"- `{item.block_name}` ({item.block_type}) at `{item.location}`: {item.why_key}"
        )
    lines.extend(["", "## Knowledge Points"])
    for item in overview.knowledge_points:
        lines.append(f"- {item}")
    lines.extend(["", "## Beginner Reading Order"])
    for item in overview.beginner_reading_order:
        lines.append(f"- {item}")
    lines.extend(["", "## Likely Confusing Points"])
    for item in overview.likely_confusing_points:
        lines.append(f"- {item}")
    lines.extend(["", "## Evidence"])
    for item in overview.evidence:
        block = f", block_id={item.block_id}" if item.block_id else ""
        line_range = f", lines={item.line_range[0]}-{item.line_range[1]}" if item.line_range else ""
        lines.append(f"- `{item.file_path}`{line_range}{block}")
    lines.append("")
    return "\n".join(lines)


def build_fallback_overview(alias: str, project: Project) -> ProjectOverview:
    slx_models = project.slx_models
    primary_model = slx_models[0] if slx_models else None
    primary_file = primary_model.file_path if primary_model is not None else project.files[0].relative_path
    blocks = list(primary_model.blocks if primary_model is not None else [])
    root_blocks = [block for block in blocks if not block.parent_subsystem]
    key_candidates = root_blocks or blocks
    key_blocks = [
        {
            "block_name": block.name,
            "block_type": block.block_type,
            "location": f"{primary_file} / {block.parent_subsystem or '<root>'}",
            "why_key": f"Represents a visible {block.block_type} block in the model structure.",
        }
        for block in key_candidates[:10]
    ]
    evidence = [
        {
            "file_path": primary_file,
            "line_range": None,
            "block_id": block.block_id if block.block_id else None,
        }
        for block in key_candidates[:3]
    ]
    while len(evidence) < 3:
        evidence.append({"file_path": primary_file, "line_range": None, "block_id": None})

    file_count = len(project.files)
    block_count = len(blocks)
    subsystem_count = len(primary_model.subsystems) if primary_model is not None else 0
    line_count = len(primary_model.lines) if primary_model is not None else 0
    model_name = primary_model.name if primary_model is not None else alias
    solver_items = list((primary_model.solver_config if primary_model is not None else {}).items())
    solver_text = ", ".join(f"{key}={value}" for key, value in solver_items[:3]) or "solver config parsed"

    key_files = [
        {"file_path": primary_file, "why_key": "Main Simulink model used as the entry point."},
        {
            "file_path": primary_file,
            "why_key": f"Contains {block_count} parsed blocks and {subsystem_count} subsystems.",
        },
        {"file_path": primary_file, "why_key": f"Contains parsed simulation settings: {solver_text}."},
    ]

    return ProjectOverview.model_validate(
        {
            "project_title": f"{alias} EE SLX",
            "project_type": PROJECT_TYPE_BY_ALIAS.get(alias, "general"),
            "one_sentence_summary": (
                f"{alias} is a Simulink-only electrical engineering model with "
                f"{block_count} blocks and {line_count} signal lines."
            )[:80],
            "main_entry_files": [
                {"file_path": primary_file, "role": f"Open this .slx model first ({model_name})."}
            ],
            "main_simulink_models": [
                {
                    "file_path": primary_file,
                    "summary": (
                        f"Parsed model {model_name} with {block_count} blocks, "
                        f"{line_count} lines, and {subsystem_count} subsystems."
                    )[:200],
                }
            ],
            "main_execution_flow": [
                f"Open `{primary_file}` and inspect the root-level signal path.",
                "Identify source, measurement, control, and power-stage blocks from names and types.",
                "Open subsystems to follow how signals are grouped and transformed.",
                "Check solver settings and key block parameters before changing the model.",
            ],
            "key_files": key_files,
            "key_blocks": key_blocks,
            "knowledge_points": [
                "Simulink signal-flow reading",
                "Electrical power conversion or machine model structure",
                "Subsystem-level model decomposition",
                "Solver and block-parameter interpretation",
            ],
            "beginner_reading_order": [
                f"Start from `{primary_file}`.",
                "Read root-level blocks and signal directions.",
                "Expand the largest subsystems and map their child blocks.",
                "Compare important block parameters with the solver configuration.",
            ],
            "likely_confusing_points": [
                "Some block names are domain abbreviations and need electrical-engineering context.",
                "Subsystem nesting can hide the real control or power-stage signal path.",
            ],
            "evidence": evidence,
        }
    )


def assert_no_absolute_paths(text: str, artifact: Path) -> None:
    markers = ["C:\\", "E:\\", "F:\\", "C:/", "E:/", "F:/", "\\Users\\asus"]
    if any(marker in text for marker in markers):
        raise ValueError(f"absolute_path_leaked:{artifact}")


async def export_overview(
    *,
    alias: str,
    project_id: str,
    project_store: SqliteProjectStore,
    overview_service: ProjectOverviewService,
) -> str:
    try:
        overview = await overview_service.get_or_generate(project_id)
        mode = "project_overview_service"
    except OverviewGenerationError:
        project = await project_store.get_project(project_id)
        overview = build_fallback_overview(alias, project)
        mode = "deterministic_local_fallback"
    json_text = json.dumps(overview.model_dump(), ensure_ascii=False, indent=2)
    md_text = overview_to_markdown(alias, overview)
    json_path = OVERVIEWS_DIR / f"{alias}.json"
    md_path = OVERVIEWS_DIR / f"{alias}.md"
    assert_no_absolute_paths(json_text, json_path)
    assert_no_absolute_paths(md_text, md_path)
    json_path.write_text(json_text + "\n", encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    return mode


async def main() -> int:
    prepare_dirs()
    if EVAL_DB_PATH.exists():
        EVAL_DB_PATH.unlink()
    await init_eval_db()

    settings = AppSettings(
        db_path=str(EVAL_DB_PATH),
        upload_dir=str(UPLOADS_DIR),
    )
    project_store = SqliteProjectStore(str(EVAL_DB_PATH))
    vector_store = SqliteVectorStore(str(EVAL_DB_PATH))
    graph_builder = ProjectGraphBuilder()
    embedder = await asyncio.to_thread(
        SentenceTransformerEmbedder,
        settings.embedding_model_name,
        settings.embedding_device,
        settings.embedding_normalize,
    )
    chunking_service = ChunkingService(
        embedder=embedder,
        vector_store=vector_store,
        graph_provider=graph_builder,
        settings=settings,
    )
    overview_service = ProjectOverviewService(
        project_store,
        InMemoryOverviewCache(),
        GeneralProjectTypeResolver(),
        DeepSeekTextProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        ),
        chunking_service=chunking_service,
    )

    built_at = datetime.utcnow().isoformat()
    project_results: dict[str, Any] = {}
    source_hashes: dict[str, str] = {}
    try:
        for alias, source in CASES:
            source_slx = resolve_source_slx(source)
            zip_path = write_alias_zip(alias, source_slx)
            source_hashes[alias] = sha256_file(zip_path)
            project_results[alias] = await ingest_one(
                alias=alias,
                zip_path=zip_path,
                settings=settings,
                project_store=project_store,
                chunking_service=chunking_service,
                vector_store=vector_store,
            )

        for alias, result in project_results.items():
            result["overview_mode"] = await export_overview(
                alias=alias,
                project_id=result["runtime_project_id"],
                project_store=project_store,
                overview_service=overview_service,
            )

        db_hash = sha256_file(EVAL_DB_PATH)
        resolved = {
            "run_id": "ad_hoc_20260608",
            "db_path": "eval/ad_hoc/eval.sqlite",
            "db_hash_or_blank": db_hash,
            "resolved_at": built_at,
            "coverage_evaluation": "ad_hoc",
            "projects": {
                alias: {
                    "runtime_project_id": result["runtime_project_id"],
                    "chunk_count": result["chunk_count"],
                    "ingest_status": result["ingest_status"],
                }
                for alias, result in project_results.items()
            },
        }
        manifest = {
            "run_id": "ad_hoc_20260608",
            "eval_db_path": "eval/ad_hoc/eval.sqlite",
            "db_hash_or_blank": db_hash,
            "source_project_aliases": [alias for alias, _ in CASES],
            "coverage_evaluation": "ad_hoc",
            "build_mode": "existing_parser_chunking_pipeline_with_relative_slx_paths",
            "built_at": built_at,
            "project_count": len(project_results),
            "all_ready": all(
                result["status"] == "ready"
                and result["chunk_count"] > 0
                and result["ingest_status"] == "ready"
                for result in project_results.values()
            ),
            "projects": {
                alias: {
                    "source_zip": f"eval/ad_hoc/inputs/{alias}.zip",
                    "source_zip_sha256": source_hashes[alias],
                    **result,
                }
                for alias, result in project_results.items()
            },
        }
        PROJECT_MAP_PATH.write_text(
            json.dumps(resolved, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        MANIFEST_PATH.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    finally:
        await chunking_service.aclose()
        await vector_store.aclose()
        await project_store.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
