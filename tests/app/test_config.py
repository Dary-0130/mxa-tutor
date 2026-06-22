import pytest
from pydantic import ValidationError

from app.config import AppSettings

ENV_KEYS = [
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DB_PATH",
    "UPLOAD_DIR",
    "UPLOAD_TTL_HOURS",
    "FREE_QUESTION_PER_PROJECT",
    "SINGLE_PACK_QUOTA",
    "MONTHLY_QUOTA",
    "MAX_UPLOAD_SIZE_MB",
    "MAX_FILES_PER_PROJECT",
    "MAX_SINGLE_FILE_MB",
    "MAX_COMPRESSION_RATIO",
    "MAX_EXTRACTION_SECONDS",
    "MAX_TOTAL_UNCOMPRESSED_MB",
    "MAX_ENTRIES_PER_PROJECT",
    "EMBEDDING_MODEL_NAME",
    "EMBEDDING_DEVICE",
    "EMBEDDING_NORMALIZE",
    "VECTOR_TOP_K",
    "VECTOR_MIN_SCORE",
    "CHUNKING_MAX_CHUNKS_PER_M_SCRIPT",
    "LOG_LEVEL",
    "APP_ENV",
    "MATLAB_BRIDGE_ENABLED",
    "MATLAB_ENGINE_ENABLED",
]


def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """清理可能污染测试的配置环境变量。"""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_default_values(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """默认值与 TASK-108 配置契约一致。"""
    _clean_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.chdir(tmp_path)

    cfg = AppSettings()

    assert cfg.deepseek_api_key == "sk-test"
    assert cfg.deepseek_base_url == "https://api.deepseek.com"
    assert cfg.embedding_model_name == "BAAI/bge-small-zh-v1.5"
    assert cfg.embedding_device == "cpu"
    assert cfg.embedding_normalize is True
    assert cfg.vector_top_k == 8
    assert cfg.vector_min_score == 0.3
    assert cfg.chunking_max_chunks_per_m_script == 80
    assert cfg.db_path == "./data/mxa.db"
    assert cfg.upload_dir == "./data/uploads"
    assert cfg.upload_ttl_hours == 24
    assert cfg.free_question_per_project == 3
    assert cfg.single_pack_quota == 100
    assert cfg.monthly_quota == 300
    assert cfg.max_upload_size_mb == 50
    assert cfg.max_files_per_project == 200
    assert cfg.max_single_file_mb == 20
    assert cfg.max_compression_ratio == 100
    assert cfg.max_extraction_seconds == 30
    assert cfg.max_total_uncompressed_mb == 200
    assert cfg.max_entries_per_project == 200
    assert cfg.log_level == "INFO"
    assert cfg.app_environment == "production"
    assert cfg.matlab_bridge_enabled is False
    assert cfg.matlab_engine_enabled is False


def test_env_override_and_type_conversion(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """环境变量覆盖配置,并自动完成 int 类型转换。"""
    _clean_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "100")
    monkeypatch.setenv("VECTOR_TOP_K", "12")
    monkeypatch.setenv("VECTOR_MIN_SCORE", "0.5")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MATLAB_BRIDGE_ENABLED", "true")
    monkeypatch.setenv("MATLAB_ENGINE_ENABLED", "true")
    monkeypatch.chdir(tmp_path)

    cfg = AppSettings()

    assert cfg.max_upload_size_mb == 100
    assert isinstance(cfg.max_upload_size_mb, int)
    assert cfg.vector_top_k == 12
    assert cfg.vector_min_score == 0.5
    assert cfg.app_environment == "test"
    assert cfg.matlab_bridge_enabled is True
    assert cfg.matlab_engine_enabled is True


@pytest.mark.parametrize(
    ("app_env", "bridge_enabled", "engine_enabled", "valid"),
    [
        ("production", "false", "false", True),
        ("development", "true", "false", True),
        ("test", "true", "false", True),
        ("production", "true", "false", True),
        ("development", "false", "true", False),
        ("test", "false", "true", False),
        ("production", "true", "true", False),
        ("development", "true", "true", True),
        ("test", "true", "true", True),
    ],
)
def test_matlab_engine_config_guard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    app_env: str,
    bridge_enabled: str,
    engine_enabled: str,
    valid: bool,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("MATLAB_BRIDGE_ENABLED", bridge_enabled)
    monkeypatch.setenv("MATLAB_ENGINE_ENABLED", engine_enabled)
    monkeypatch.chdir(tmp_path)

    if valid:
        cfg = AppSettings()
        assert cfg.app_environment == app_env
        assert cfg.matlab_bridge_enabled is (bridge_enabled == "true")
        assert cfg.matlab_engine_enabled is (engine_enabled == "true")
    else:
        with pytest.raises(ValidationError):
            AppSettings()


def test_missing_required_raises(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """缺少 DEEPSEEK_API_KEY 时抛 ValidationError。"""
    _clean_env(monkeypatch)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError):
        AppSettings()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("VECTOR_TOP_K", "0"),
        ("VECTOR_TOP_K", "51"),
        ("VECTOR_MIN_SCORE", "-1.1"),
        ("VECTOR_MIN_SCORE", "1.1"),
        ("CHUNKING_MAX_CHUNKS_PER_M_SCRIPT", "0"),
        ("CHUNKING_MAX_CHUNKS_PER_M_SCRIPT", "101"),
    ],
)
def test_vector_bounds_raise(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    key: str,
    value: str,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError):
        AppSettings()


def test_invalid_type_raises(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """无法转换成 int 的环境变量值会抛 ValidationError。"""
    _clean_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "not-a-number")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError):
        AppSettings()
