"""aiosqlite 连接管理 helper(TASK-204)。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


@asynccontextmanager
async def open_connection(db_path: str) -> AsyncIterator[aiosqlite.Connection]:
    """打开 aiosqlite 连接,配置 PRAGMA 后 yield,退出时关闭。"""

    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(db_path)
    try:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA secure_delete=ON")
        yield conn
    finally:
        await conn.close()
