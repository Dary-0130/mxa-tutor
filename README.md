# mxa-tutor

不是从零学 MATLAB,而是把你手上的工程讲明白。拖一个工程进来,带你看懂、问答到底。

## 快速启动

1. 克隆仓库:
   ```bash
   git clone git@github.com:Dary-0130/mxa-tutor.git
   cd mxa-tutor
   ```
2. 创建虚拟环境:
   ```bash
   python -m venv .venv
   ```
3. 激活虚拟环境:
   ```bash
   source .venv/bin/activate
   ```
   Windows:
   ```powershell
   .venv\Scripts\activate
   ```
4. 安装开发依赖:
   ```bash
   pip install -r requirements-dev.txt
   ```
5. 运行本地检查:
   ```bash
   make test
   make hygiene
   make check
   ```

Windows 用户请在 Git Bash 或 WSL 内执行 `make` 命令。

本仓库使用 GitHub Actions 在每个 PR 上运行 lint、format check、type-check、
test 和仓库卫生检查。所有 PR 必须 CI 全绿后才能合并。

## Chat RAG

问答链路默认走 `HybridRetriever`:优先用本地 embedding + SQLite chunks 做向量召回,
当 chunks 未就绪或向量链路失败时自动降级到关键词检索。阈值可通过
`RAG_MIN_CHUNK_COUNT` 配置,默认 `1`。

## 文档导航

- [项目宪法](docs/01_PROJECT_CONSTITUTION.md)
- [架构总览](docs/02_ARCHITECTURE_OVERVIEW.md)
- [Task 总览](docs/03_TASK_INDEX.md)
- [工程规范](docs/04_ENGINEERING_STANDARDS.md)
- [教学输出风格规范](docs/05_EXPLANATION_STYLE_GUIDE.md)
