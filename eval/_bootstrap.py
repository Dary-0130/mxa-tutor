"""Eval-only ChatService wiring and recording wrappers for TASK-306."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedder
from adapters.llm import DeepSeekTextProvider
from adapters.storage.sqlite_chat_store import SqliteChatStore
from adapters.storage.sqlite_project_store import SqliteProjectStore
from adapters.storage.sqlite_vector_store import SqliteVectorStore
from app.config import AppSettings
from core.interfaces.llm_provider import LLMResponse, ModelCapability, TextProvider
from features.chat import HybridRetriever, KeywordRetriever, VectorRetriever
from features.chat import _prompt_builder as chat_prompt_builder_module
from features.chat._prompt_builder import ChatPromptBuilder
from features.chat._prompt_loader import PromptTemplate
from features.chat._retriever import Retriever
from features.chat.chat_schemas import ChatResponse
from features.chat.chat_service import ChatService
from features.overview.project_graph_builder import ProjectGraphBuilder

SOURCE_TABLE_CAPTURE_PROMPT_BUILDER = "prompt_builder_source_entries"
SOURCE_TABLE_CAPTURE_UNAVAILABLE = "unavailable"


class RecordingRetriever(Retriever):
    """Record retrieval hits for diagnostics only."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.last_hits: list[Any] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    async def search(self, *args: Any, **kwargs: Any) -> list[Any]:
        hits = await self.inner.search(*args, **kwargs)
        self.last_hits = list(hits)
        return hits

    def reset(self) -> None:
        self.last_hits = []


class RecordingTextProvider(TextProvider):
    """Record the raw LLM response text and provider latency."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.last_raw_response_text: str | None = None
        self.last_llm_duration_ms: int | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def chat(self, *args: Any, **kwargs: Any) -> LLMResponse:
        start = time.perf_counter()
        result = self.inner.chat(*args, **kwargs)
        self.last_llm_duration_ms = int((time.perf_counter() - start) * 1000)
        self.last_raw_response_text = result.text
        return result

    def capability(self) -> ModelCapability:
        return self.inner.capability()

    def reset(self) -> None:
        self.last_raw_response_text = None
        self.last_llm_duration_ms = None


class RecordingPromptBuilder(ChatPromptBuilder):
    """Capture the exact source_entries received by ChatPromptBuilder."""

    def __init__(self, inner: ChatPromptBuilder, prompt_path: Path, template: PromptTemplate) -> None:
        self.inner = inner
        self.prompt_path = prompt_path
        self.template = template
        self.last_source_entries: list[Any] = []
        self.last_source_table: list[dict[str, str]] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def build_messages(self, *args: Any, **kwargs: Any) -> Any:
        source_entries = _extract_source_entries_from_call(args, kwargs)
        self.last_source_entries = source_entries
        self.last_source_table = _derive_source_table(source_entries)

        module = cast(Any, chat_prompt_builder_module)
        original_loader = module.load_prompt_template
        module.load_prompt_template = lambda filename="qa_with_context.yaml": self.template
        try:
            return self.inner.build_messages(*args, **kwargs)
        finally:
            module.load_prompt_template = original_loader

    def reset(self) -> None:
        self.last_source_entries = []
        self.last_source_table = []


@dataclass
class EvalAuditContext:
    """Per-run audit context used by eval scripts."""

    loaded_prompt_path: str
    loaded_prompt_version: str
    prompt_loader_mode: str
    recording_retriever: RecordingRetriever
    recording_text_provider: RecordingTextProvider
    recording_prompt_builder: RecordingPromptBuilder
    project_store: SqliteProjectStore
    chat_store: SqliteChatStore
    vector_store: SqliteVectorStore
    model_name: str

    def reset_case(self) -> None:
        self.recording_retriever.reset()
        self.recording_text_provider.reset()
        self.recording_prompt_builder.reset()

    def collect_per_case_audit(self, response: ChatResponse | None = None) -> dict[str, Any]:
        source_table = list(self.recording_prompt_builder.last_source_table)
        capture_mode = (
            SOURCE_TABLE_CAPTURE_PROMPT_BUILDER if source_table else SOURCE_TABLE_CAPTURE_UNAVAILABLE
        )
        raw_ids, raw_ids_available = _extract_raw_citation_ids(
            self.recording_text_provider.last_raw_response_text
        )
        returned_refs = _response_citation_refs(response)
        raw_id_type_map = _raw_id_type_map(raw_ids, raw_ids_available, source_table)
        returned_types = _returned_citation_types(returned_refs, source_table)
        citation_type_source = _citation_type_source(
            raw_ids_available=raw_ids_available,
            source_table=source_table,
            raw_id_type_map=raw_id_type_map,
            returned_types=returned_types,
        )

        return {
            "raw_citation_ids_json": _json(raw_ids if raw_ids_available else []),
            "source_table_json": _json(source_table),
            "source_table_capture_mode": capture_mode,
            "raw_citation_id_type_map_json": _json(raw_id_type_map),
            "returned_citation_refs_json": _json(returned_refs),
            "returned_citation_types_json_or_blank": _json(returned_types) if returned_types else "",
            "returned_citation_count": len(returned_refs),
            "retrieval_hit_types_json": _json(
                [str(getattr(hit, "source_type", "")) for hit in self.recording_retriever.last_hits]
            ),
            "citation_type_source": citation_type_source,
            "fallback_reason_or_blank": _response_fallback_reason(response),
            "session_id": response.session_id if response is not None else "",
            "llm_duration_ms": self.recording_text_provider.last_llm_duration_ms or "",
        }

    async def aclose(self) -> None:
        await self.vector_store.aclose()
        await self.chat_store.aclose()
        await self.project_store.aclose()


def build_chat_service_for_eval(
    prompt_path: Path,
    eval_db_path: Path,
) -> tuple[ChatService, EvalAuditContext]:
    """Build an eval-only ChatService wired to the supplied prompt and SQLite DB."""

    prompt_path = _resolve_existing_path(prompt_path)
    eval_db_path = _resolve_eval_db_path(eval_db_path)
    template = _load_prompt_template_from_path(prompt_path)
    settings = AppSettings(db_path=str(eval_db_path))  # type: ignore[call-arg]

    project_store = SqliteProjectStore(settings.db_path)
    chat_store = SqliteChatStore(settings.db_path)
    graph_provider = ProjectGraphBuilder()
    embedder = SentenceTransformerEmbedder(
        settings.embedding_model_name,
        settings.embedding_device,
        settings.embedding_normalize,
    )
    vector_store = SqliteVectorStore(settings.db_path)
    keyword_retriever = KeywordRetriever(graph_provider=graph_provider)
    vector_retriever = VectorRetriever(
        embedder=embedder,
        vector_store=vector_store,
        min_score=settings.vector_min_score,
    )
    hybrid_retriever = HybridRetriever(
        vector=vector_retriever,
        keyword=keyword_retriever,
        vector_store=vector_store,
        min_chunk_count=settings.rag_min_chunk_count,
    )
    recording_retriever = RecordingRetriever(hybrid_retriever)

    text_provider = DeepSeekTextProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    recording_text_provider = RecordingTextProvider(text_provider)
    recording_prompt_builder = RecordingPromptBuilder(
        inner=ChatPromptBuilder(),
        prompt_path=prompt_path,
        template=template,
    )
    chat_service = ChatService(
        project_store=project_store,
        chat_store=chat_store,
        text_provider=recording_text_provider,
        retriever=recording_retriever,
        prompt_builder=recording_prompt_builder,
    )
    audit = EvalAuditContext(
        loaded_prompt_path=str(prompt_path),
        loaded_prompt_version=template.version,
        prompt_loader_mode="eval_wrapper",
        recording_retriever=recording_retriever,
        recording_text_provider=recording_text_provider,
        recording_prompt_builder=recording_prompt_builder,
        project_store=project_store,
        chat_store=chat_store,
        vector_store=vector_store,
        model_name=text_provider.capability().model_name,
    )
    return chat_service, audit


def _resolve_existing_path(path: Path) -> Path:
    resolved = path if path.is_absolute() else ROOT / path
    resolved = resolved.resolve()
    if not resolved.exists():
        raise FileNotFoundError("prompt_path_missing")
    return resolved


def _resolve_eval_db_path(path: Path) -> Path:
    resolved = path if path.is_absolute() else ROOT / path
    resolved = resolved.resolve()
    default_db = (ROOT / "data" / "mxa.db").resolve()
    if resolved == default_db:
        raise ValueError("eval_db_path_must_not_be_default_data_db")
    if not resolved.exists():
        raise FileNotFoundError("eval_db_path_missing")
    return resolved


def _load_prompt_template_from_path(path: Path) -> PromptTemplate:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("prompt_template_must_be_mapping")
    return PromptTemplate(
        version=_required_str(data, "version"),
        description=_required_str(data, "description"),
        system=_required_str(data, "system"),
        user=_required_str(data, "user"),
    )


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("prompt_template_field_missing")
    return value


def _extract_source_entries_from_call(args: tuple[Any, ...], kwargs: dict[str, Any]) -> list[Any]:
    try:
        source_entries = kwargs.get("source_entries")
        if source_entries is None and len(args) >= 2:
            source_entries = args[1]
        return list(source_entries or [])
    except Exception:
        return []


def _derive_source_table(source_entries: list[Any]) -> list[dict[str, str]]:
    table: list[dict[str, str]] = []
    for entry in source_entries:
        try:
            source_ref = entry.source_ref
            source_type = str(entry.hit.source_type)
            table.append(
                {
                    "source_id": str(entry.source_id),
                    "source_type": source_type,
                    "source_ref_key": _source_ref_key(source_type, source_ref),
                    "file_path": str(getattr(source_ref, "file_path", "") or ""),
                    "block_name": str(getattr(source_ref, "block_name", "") or ""),
                    "function_name": "",
                    "parameter_name": str(getattr(source_ref, "parameter_name", "") or ""),
                }
            )
        except Exception:
            continue
    return table


def _source_ref_key(source_type: str, ref: Any) -> str:
    parts = [source_type, str(getattr(ref, "file_path", "") or "")]
    line_range = getattr(ref, "line_range", None)
    if line_range:
        parts.append(f"lines={line_range[0]}-{line_range[1]}")
    block_name = getattr(ref, "block_name", None)
    if block_name:
        parts.append(f"block={block_name}")
    parent = getattr(ref, "parent_subsystem", None)
    if parent:
        parts.append(f"parent={parent}")
    parameter = getattr(ref, "parameter_name", None)
    if parameter:
        parts.append(f"param={parameter}")
    return "::".join(parts)


def _extract_raw_citation_ids(raw_text: str | None) -> tuple[list[str], bool]:
    if not raw_text:
        return [], False
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return [], False
    citation_ids = payload.get("citation_ids") if isinstance(payload, dict) else None
    if not isinstance(citation_ids, list):
        return [], False
    return [str(item) for item in citation_ids if isinstance(item, str)], True


def _response_citation_refs(response: ChatResponse | None) -> list[dict[str, Any]]:
    if response is None:
        return []
    return [
        {
            key: value
            for key, value in citation.model_dump().items()
            if value not in (None, "", [])
        }
        for citation in response.citations
    ]


def _raw_id_type_map(
    raw_ids: list[str],
    raw_ids_available: bool,
    source_table: list[dict[str, str]],
) -> dict[str, str]:
    if not raw_ids_available or not source_table:
        return {}
    by_id = {row["source_id"]: row["source_type"] for row in source_table}
    return {source_id: by_id[source_id] for source_id in raw_ids if source_id in by_id}


def _returned_citation_types(
    returned_refs: list[dict[str, Any]],
    source_table: list[dict[str, str]],
) -> list[str]:
    types: list[str] = []
    for ref in returned_refs:
        matched = _match_source_table_row(ref, source_table)
        if matched is not None:
            types.append(matched["source_type"])
    return types


def _match_source_table_row(
    ref: dict[str, Any],
    source_table: list[dict[str, str]],
) -> dict[str, str] | None:
    for row in source_table:
        if str(ref.get("file_path", "")) != row.get("file_path", ""):
            continue
        if ref.get("block_name") and str(ref.get("block_name")) != row.get("block_name", ""):
            continue
        if ref.get("parameter_name") and str(ref.get("parameter_name")) != row.get(
            "parameter_name", ""
        ):
            continue
        return row
    return None


def _citation_type_source(
    *,
    raw_ids_available: bool,
    source_table: list[dict[str, str]],
    raw_id_type_map: dict[str, str],
    returned_types: list[str],
) -> str:
    if not source_table:
        return "unavailable"
    if raw_ids_available and raw_id_type_map is not None:
        return "raw_llm"
    if returned_types:
        return "recording_prompt_builder_match"
    return "unavailable"


def _response_fallback_reason(response: ChatResponse | None) -> str:
    if response is None or response.fallback_reason is None:
        return ""
    return str(response.fallback_reason)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _smoke_loaded_audit(args: argparse.Namespace) -> int:
    original_loader = chat_prompt_builder_module.load_prompt_template
    _, baseline = build_chat_service_for_eval(args.baseline_prompt, args.eval_db_path)
    _, rc = build_chat_service_for_eval(args.rc_prompt, args.eval_db_path)
    if baseline.loaded_prompt_version != "v0.1":
        raise AssertionError("baseline_loaded_prompt_version_not_v0.1")
    if rc.loaded_prompt_version != "v0.2-rc":
        raise AssertionError("rc_loaded_prompt_version_not_v0.2-rc")
    if chat_prompt_builder_module.load_prompt_template is not original_loader:
        raise AssertionError("prompt_loader_monkeypatch_not_restored")
    print(
        "loaded audit PASS: "
        f"baseline={baseline.loaded_prompt_version} rc={rc.loaded_prompt_version} "
        f"mode={rc.prompt_loader_mode}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TASK-306 eval bootstrap helpers")
    parser.add_argument("--smoke-loaded-audit", action="store_true")
    parser.add_argument("--baseline-prompt", type=Path)
    parser.add_argument("--rc-prompt", type=Path)
    parser.add_argument("--eval-db-path", type=Path)
    args = parser.parse_args()
    if args.smoke_loaded_audit:
        missing = [
            name
            for name in ("baseline_prompt", "rc_prompt", "eval_db_path")
            if getattr(args, name) is None
        ]
        if missing:
            parser.error(f"missing required smoke args: {', '.join(missing)}")
        return _smoke_loaded_audit(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
