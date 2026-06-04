from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from adapters.storage._connection import open_connection
from adapters.storage.schema import init_schema
from adapters.storage.sqlite_chat_store import SqliteChatStore
from adapters.storage.sqlite_project_store import SqliteProjectStore


@pytest.fixture
def db_path(tmp_path) -> str:
    return str(tmp_path / "test.db")


@pytest_asyncio.fixture
async def initialized_db_path(db_path: str) -> AsyncIterator[str]:
    async with open_connection(db_path) as conn:
        await init_schema(conn)
    yield db_path


@pytest_asyncio.fixture
async def project_store(initialized_db_path: str) -> SqliteProjectStore:
    return SqliteProjectStore(initialized_db_path)


@pytest_asyncio.fixture
async def chat_store(initialized_db_path: str) -> SqliteChatStore:
    return SqliteChatStore(initialized_db_path)
