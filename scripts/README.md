# scripts

一次性脚本与仓库维护脚本。

当前包含 `check_repo_hygiene.sh`,用于本地和 CI 中检查仓库卫生:基础配置字段、
敏感 key 模式、TODO 残留、`print(` 调用和裸 `except:`。

未来会按 Task 增加 `init_db.py`、`dev_setup.py` 等一次性初始化脚本。详见
`docs/02_ARCHITECTURE_OVERVIEW.md` 第 3 节。
