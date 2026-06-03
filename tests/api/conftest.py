"""tests/api 共享 fixture。"""

from collections.abc import Iterator

import pytest

from api.dependencies import get_settings


@pytest.fixture(autouse=True)
def _isolate_test_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """测试前后清理 ``get_settings`` 缓存 + ``dependency_overrides``。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-for-test")
    get_settings.cache_clear()

    from api.main import app

    app.dependency_overrides.clear()

    yield

    get_settings.cache_clear()

    leaked = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    if leaked:
        import sys

        print(
            f"WARNING: test leaked dependency_overrides: {list(leaked.keys())}",
            file=sys.stderr,
        )
