"""项目全局配置(pydantic-settings 加载自 .env 或环境变量)。"""

from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """项目全局配置。下游通过 ``from app.config import AppSettings`` 消费。

    所有字段从环境变量或 .env 文件加载。字段名小写,环境变量名大写
    (例如 ``max_upload_size_mb`` 对应 ``MAX_UPLOAD_SIZE_MB``)。
    """

    # LLM
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"

    # Embedding(TASK-301 新增)
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    embedding_device: str = "cpu"
    embedding_normalize: bool = True

    # Vector(TASK-302 新增)
    vector_top_k: int = Field(default=8, ge=1, le=50)
    vector_min_score: float = Field(default=0.3, ge=-1.0, le=1.0)

    # RAG retrieval(TASK-304 新增)
    rag_min_chunk_count: int = Field(
        default=1,
        ge=0,
        le=100,
        description=(
            "HybridRetriever 触发 keyword fallback 的 chunk 数阈值;"
            "vector_store.get_chunk_count(project_id) < rag_min_chunk_count 时降级"
        ),
    )

    # Chunking(TASK-303 新增)
    chunking_max_source_text_chars: int = Field(default=1024, ge=64, le=4096)
    chunking_docstring_max_chars: int = Field(default=300, ge=0, le=1000)
    chunking_param_value_max_chars: int = Field(default=80, ge=0, le=500)
    chunking_max_params_per_block: int = Field(default=12, ge=0, le=50)
    chunking_max_subsystem_child_block_names: int = Field(default=20, ge=0, le=100)
    chunking_description_max_chars: int = Field(default=300, ge=0, le=1000)
    chunking_max_chunks_per_m_script: int = Field(default=80, ge=1, le=100)

    # Storage
    db_path: str = "./data/mxa.db"
    upload_dir: str = "./data/uploads"
    upload_ttl_hours: int = 24

    # Quota
    free_question_per_project: int = 3
    single_pack_quota: int = 100
    monthly_quota: int = 300

    # File limits(基础)
    max_upload_size_mb: int = 50
    max_files_per_project: int = 200
    max_single_file_mb: int = 20
    max_compression_ratio: int = 100

    # File limits(TASK-104 扩展)
    max_extraction_seconds: int = 30
    max_total_uncompressed_mb: int = 200
    max_entries_per_project: int = 200

    # Logging
    log_level: str = "INFO"

    # MATLAB Add-on bridge(TASK-510)
    app_environment: Literal["production", "development", "test"] = Field(
        default="production",
        validation_alias="APP_ENV",
    )
    matlab_bridge_enabled: bool = False
    matlab_engine_enabled: bool = Field(default=False, validation_alias="MATLAB_ENGINE_ENABLED")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _validate_matlab_engine_guard(self) -> Self:
        if not self.matlab_engine_enabled:
            return self
        if not self.matlab_bridge_enabled:
            raise ValueError("matlab_engine_enabled requires MATLAB_BRIDGE_ENABLED=true")
        if self.app_environment not in {"development", "test"}:
            raise ValueError("matlab_engine_enabled requires APP_ENV=development or APP_ENV=test")
        return self
