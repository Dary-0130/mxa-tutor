import pytest
from pydantic import ValidationError

from app.config import AppSettings

TEST_BRIDGE_SIGNING_KEY = "test-bridge-signing-key-32-bytes-ok"
TEST_BRIDGE_BOOTSTRAP_TOKEN = "test-bridge-bootstrap-token-32-bytes"

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
    "MATLAB_BRIDGE_AUTH_SIGNING_KEY",
    "MATLAB_BRIDGE_AUTH_KEY_ID",
    "MATLAB_BRIDGE_AUTH_ISSUER",
    "MATLAB_BRIDGE_AUTH_AUDIENCE",
    "MATLAB_BRIDGE_AUTH_TOKEN_TTL_SECONDS",
    "MATLAB_BRIDGE_AUTH_MAX_LIFETIME_SECONDS",
    "MATLAB_BRIDGE_AUTH_CLOCK_SKEW_SECONDS",
    "MATLAB_BRIDGE_WORKER_COUNT",
    "WEB_CONCURRENCY",
    "UVICORN_WORKERS",
    "MATLAB_BRIDGE_INSTANCE_COUNT",
    "MATLAB_BRIDGE_DEV_AUTH_ENABLED",
    "MATLAB_BRIDGE_DEV_AUTH_BOOTSTRAP_TOKEN",
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
    assert cfg.matlab_bridge_auth_signing_key is None
    assert cfg.matlab_bridge_auth_key_id == "mxa-bridge-dev-v1"
    assert cfg.matlab_bridge_auth_issuer == "mxa-tutor-dev"
    assert cfg.matlab_bridge_auth_audience == "mxa-matlab-bridge"
    assert cfg.matlab_bridge_auth_token_ttl_seconds == 300
    assert cfg.matlab_bridge_auth_max_lifetime_seconds == 900
    assert cfg.matlab_bridge_auth_clock_skew_seconds == 10
    assert cfg.matlab_bridge_worker_count == 1
    assert cfg.matlab_bridge_instance_count == 1
    assert cfg.matlab_bridge_dev_auth_enabled is False
    assert cfg.matlab_bridge_dev_auth_bootstrap_token is None


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
    monkeypatch.setenv("MATLAB_BRIDGE_AUTH_SIGNING_KEY", TEST_BRIDGE_SIGNING_KEY)
    monkeypatch.setenv("MATLAB_BRIDGE_AUTH_TOKEN_TTL_SECONDS", "120")
    monkeypatch.chdir(tmp_path)

    cfg = AppSettings()

    assert cfg.max_upload_size_mb == 100
    assert isinstance(cfg.max_upload_size_mb, int)
    assert cfg.vector_top_k == 12
    assert cfg.vector_min_score == 0.5
    assert cfg.app_environment == "test"
    assert cfg.matlab_bridge_enabled is True
    assert cfg.matlab_engine_enabled is True
    assert cfg.matlab_bridge_auth_token_ttl_seconds == 120


@pytest.mark.parametrize(
    ("app_env", "bridge_enabled", "engine_enabled", "valid"),
    [
        ("production", "false", "false", True),
        ("development", "true", "false", True),
        ("test", "true", "false", True),
        ("production", "true", "false", False),
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
    if bridge_enabled == "true":
        monkeypatch.setenv("MATLAB_BRIDGE_AUTH_SIGNING_KEY", TEST_BRIDGE_SIGNING_KEY)
    monkeypatch.chdir(tmp_path)

    if valid:
        cfg = AppSettings()
        assert cfg.app_environment == app_env
        assert cfg.matlab_bridge_enabled is (bridge_enabled == "true")
        assert cfg.matlab_engine_enabled is (engine_enabled == "true")
    else:
        with pytest.raises(ValidationError):
            AppSettings()


@pytest.mark.parametrize("signing_key", [None, "short", "default", "replace-me"])
def test_matlab_bridge_signing_key_guard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    signing_key: str | None,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MATLAB_BRIDGE_ENABLED", "true")
    if signing_key is None:
        monkeypatch.delenv("MATLAB_BRIDGE_AUTH_SIGNING_KEY", raising=False)
    else:
        monkeypatch.setenv("MATLAB_BRIDGE_AUTH_SIGNING_KEY", signing_key)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError):
        AppSettings()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("MATLAB_BRIDGE_WORKER_COUNT", "2"),
        ("WEB_CONCURRENCY", "2"),
        ("UVICORN_WORKERS", "2"),
        ("MATLAB_BRIDGE_INSTANCE_COUNT", "2"),
    ],
)
def test_matlab_bridge_single_worker_single_instance_guard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    key: str,
    value: str,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MATLAB_BRIDGE_ENABLED", "true")
    monkeypatch.setenv("MATLAB_BRIDGE_AUTH_SIGNING_KEY", TEST_BRIDGE_SIGNING_KEY)
    monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError):
        AppSettings()


def test_dev_bridge_auth_requires_bootstrap_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MATLAB_BRIDGE_ENABLED", "true")
    monkeypatch.setenv("MATLAB_BRIDGE_AUTH_SIGNING_KEY", TEST_BRIDGE_SIGNING_KEY)
    monkeypatch.setenv("MATLAB_BRIDGE_DEV_AUTH_ENABLED", "true")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError):
        AppSettings()

    monkeypatch.setenv("MATLAB_BRIDGE_DEV_AUTH_BOOTSTRAP_TOKEN", TEST_BRIDGE_BOOTSTRAP_TOKEN)
    cfg = AppSettings()
    assert cfg.matlab_bridge_dev_auth_enabled is True


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
