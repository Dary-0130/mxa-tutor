"""Keyword retriever for coarse chat RAG."""

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Literal, Protocol

from core.domain.project import Project
from core.domain.project_graph import ProjectGraph
from core.domain.source_ref import SourceRef

SourceType = Literal["file", "block", "function", "param", "graph_entry", "unresolved"]


class ProjectGraphProvider(Protocol):
    """Build a project graph from parser metadata."""

    def build(self, project: Project) -> ProjectGraph:
        """Build a graph."""
        ...


@dataclass(frozen=True)
class RetrievalHit:
    """Single retriever hit."""

    source_ref: SourceRef
    score: float
    snippet: str
    source_type: SourceType
    block_type: str | None = None


@dataclass(frozen=True)
class SourceEntry:
    """Retrieval hit with stable source_id and validation metadata."""

    source_id: str
    hit: RetrievalHit
    source_ref: SourceRef
    snippet: str
    validation_key: tuple[str, str, str, str] | None


@dataclass(frozen=True)
class _Candidate:
    source_ref: SourceRef
    source_type: SourceType
    snippet: str
    weighted_texts: tuple[tuple[str, float], ...]
    block_type: str | None = None


class Retriever(ABC):
    """Retriever interface used by ChatService."""

    @abstractmethod
    async def search(self, project: Project, query: str, top_k: int = 8) -> list[RetrievalHit]:
        """Search project metadata."""
        ...


class KeywordRetriever(Retriever):
    """Simple metadata keyword retriever."""

    _WEIGHT_FILE_NAME = 5.0
    _WEIGHT_BLOCK_NAME = 4.0
    _WEIGHT_FUNCTION_NAME = 4.0
    _WEIGHT_PARAM_NAME = 3.0
    _WEIGHT_PARAM_VALUE = 2.5
    _WEIGHT_BLOCK_TYPE = 2.0
    _WEIGHT_GRAPH_ENTRY = 2.0
    _WEIGHT_DOCSTRING_OR_DESC = 1.0
    _PARAM_VALUE_MAX_CHARS = 80
    _SNIPPET_MAX_CHARS = 300
    _MIN_SCORE = 1.5
    _MAX_TOP_K = 12
    _DOMAIN_ALIASES: dict[str, list[str]] = {
        "速度环": ["speed", "speedloop", "speed_controller", "speedcontroller", "omega_loop"],
        "电流环": ["current", "currentloop", "current_controller", "currentcontroller"],
        "转速": ["speed", "rpm", "omega", "n_motor"],
        "比例": ["kp", "p_gain", "proportional"],
        "积分": ["ki", "i_gain", "integral"],
        "微分": ["kd", "d_gain", "derivative"],
        "入口": ["main", "run", "startup", "entry", "init"],
        "参数": ["param", "params", "parameter", "config"],
        "仿真": ["sim", "simulate", "simulation"],
        "电机": ["motor", "machine", "pmsm", "im", "induction"],
        "控制器": ["controller", "ctrl", "regulator"],
    }

    def __init__(self, graph_provider: ProjectGraphProvider) -> None:
        self._graph_provider = graph_provider

    async def search(self, project: Project, query: str, top_k: int = 8) -> list[RetrievalHit]:
        top_k_capped = min(max(top_k, 0), self._MAX_TOP_K)
        return await asyncio.to_thread(self._search_sync, project, query, top_k_capped)

    def _search_sync(self, project: Project, query: str, top_k: int) -> list[RetrievalHit]:
        tokens = _tokenize(query)
        if not tokens or top_k == 0:
            return []
        graph = self._graph_provider.build(project)
        candidates = self._gather_candidates(project, graph)
        scored = [
            hit
            for hit in self._score_candidates(candidates, tokens)
            if hit.score >= self._MIN_SCORE
        ]
        scored.sort(key=lambda hit: -hit.score)
        return _dedupe_by_source_ref(scored)[:top_k]

    def _gather_candidates(self, project: Project, graph: ProjectGraph) -> list[_Candidate]:
        candidates: list[_Candidate] = []
        for file_info in project.files:
            description = file_info.description or ""
            candidates.append(
                _Candidate(
                    source_ref=SourceRef(file_path=file_info.relative_path),
                    source_type="file",
                    snippet=_truncate(
                        f"文件 {file_info.relative_path},类型 {file_info.file_type}。{description}"
                    ),
                    weighted_texts=(
                        (file_info.relative_path, self._WEIGHT_FILE_NAME),
                        (description, self._WEIGHT_DOCSTRING_OR_DESC),
                    ),
                )
            )
        for m_file in project.m_files:
            for func in m_file.functions:
                candidates.append(
                    _Candidate(
                        source_ref=SourceRef(
                            file_path=m_file.file_path, line_range=func.line_range
                        ),
                        source_type="function",
                        snippet=_truncate(
                            f"函数 {func.name} 位于 {m_file.file_path},输入 {func.inputs},"
                            f"输出 {func.outputs}。{func.docstring or ''}"
                        ),
                        weighted_texts=(
                            (m_file.file_path, self._WEIGHT_FILE_NAME),
                            (func.name, self._WEIGHT_FUNCTION_NAME),
                            (" ".join(func.inputs + func.outputs), self._WEIGHT_PARAM_NAME),
                            (func.docstring or "", self._WEIGHT_DOCSTRING_OR_DESC),
                        ),
                    )
                )
        for model in project.slx_models:
            for block in model.blocks:
                parent = block.parent_subsystem or "<root>"
                params = " ".join(
                    f"{key}={str(value)[: self._PARAM_VALUE_MAX_CHARS]}"
                    for key, value in block.parameters.items()
                )
                candidates.append(
                    _Candidate(
                        source_ref=SourceRef(
                            file_path=model.file_path,
                            block_id=block.block_id,
                            block_name=block.name,
                            parent_subsystem=block.parent_subsystem,
                        ),
                        source_type="block",
                        snippet=_truncate(
                            f"Block {block.name}({block.block_type}) 位于 {model.file_path}/{parent},"
                            f"参数 {params}"
                        ),
                        weighted_texts=(
                            (model.file_path, self._WEIGHT_FILE_NAME),
                            (block.name, self._WEIGHT_BLOCK_NAME),
                            (block.block_type, self._WEIGHT_BLOCK_TYPE),
                            (" ".join(block.parameters), self._WEIGHT_PARAM_NAME),
                            (params, self._WEIGHT_PARAM_VALUE),
                            (parent, self._WEIGHT_DOCSTRING_OR_DESC),
                        ),
                        block_type=block.block_type,
                    )
                )
        candidates.extend(self._graph_candidates(project, graph))
        return candidates

    def _graph_candidates(self, project: Project, graph: ProjectGraph) -> list[_Candidate]:
        file_paths = {file_info.relative_path for file_info in project.files}
        fallback_path = next(iter(file_paths), project.name)
        candidates: list[_Candidate] = []
        for entry in graph.entry_points + graph.execution_flow:
            file_path = entry if entry in file_paths else fallback_path
            candidates.append(
                _Candidate(
                    source_ref=SourceRef(file_path=file_path),
                    source_type="graph_entry",
                    snippet=_truncate(f"工程执行入口或流程节点:{entry}"),
                    weighted_texts=((entry, self._WEIGHT_GRAPH_ENTRY),),
                )
            )
        for symbol in graph.unresolved_symbols:
            candidates.append(
                _Candidate(
                    source_ref=SourceRef(file_path=fallback_path),
                    source_type="unresolved",
                    snippet=_truncate(f"未解析符号:{symbol}"),
                    weighted_texts=((symbol, self._WEIGHT_GRAPH_ENTRY),),
                )
            )
        return candidates

    def _score_candidates(
        self, candidates: list[_Candidate], tokens: list[str]
    ) -> list[RetrievalHit]:
        query_tokens = set(tokens)
        hits: list[RetrievalHit] = []
        for candidate in candidates:
            score = 0.0
            for text, weight in candidate.weighted_texts:
                if not text:
                    continue
                score += len(query_tokens & set(_tokenize(text))) * weight
            if score > 0:
                hits.append(
                    RetrievalHit(
                        source_ref=candidate.source_ref,
                        score=score,
                        snippet=candidate.snippet,
                        source_type=candidate.source_type,
                        block_type=candidate.block_type,
                    )
                )
        return hits


def _tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese, English, and MATLAB identifiers."""
    tokens: list[str] = []
    for cn_term, en_aliases in KeywordRetriever._DOMAIN_ALIASES.items():
        if cn_term in text:
            tokens.extend(en_aliases)
    identifiers = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
    for ident in identifiers:
        tokens.append(ident.lower())
        for part in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", ident):
            tokens.append(part.lower())
        for part in re.split(r"[_/]", ident):
            if part:
                tokens.append(part.lower())
    cn_chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    tokens.extend(cn_chars)
    tokens.extend(cn_chars[index] + cn_chars[index + 1] for index in range(len(cn_chars) - 1))
    deduped = list(dict.fromkeys(tokens))
    return [token for token in deduped if len(token) >= 2 or _starts_with_chinese(token)]


def _starts_with_chinese(token: str) -> bool:
    return bool(token) and "\u4e00" <= token[0] <= "\u9fff"


def _truncate(text: str, max_chars: int = KeywordRetriever._SNIPPET_MAX_CHARS) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized[:max_chars]


def _dedupe_by_source_ref(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    seen: set[tuple[tuple[str, object], ...]] = set()
    deduped: list[RetrievalHit] = []
    for hit in hits:
        key = tuple(sorted(asdict(hit.source_ref).items()))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return deduped
