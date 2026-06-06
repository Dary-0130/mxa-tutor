"""项目全局配置(pydantic-settings 加载自 .env 或环境变量)。"""

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
