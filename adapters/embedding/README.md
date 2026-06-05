# adapters/embedding

EmbeddingProvider 实现层,把 sentence-transformers 接入 mxa-tutor。

## 当前实现

- `SentenceTransformerEmbedder` — 基于 `BAAI/bge-small-zh-v1.5`(中文,~100MB,CPU 推理),实现 `core/interfaces/embedder.py::EmbeddingProvider`。

## 装配

本 Task(TASK-301)只实现 adapter 类,不在 lifespan 装配 `app.state.embedder`。
TASK-302(SQLite 向量存储)/ TASK-304(向量 RAG 整合)接通时再装配 lifespan +
`api/dependencies.py::get_embedder()`。

## 模型缓存

走 HuggingFace 默认路径 `~/.cache/huggingface/`。首次加载需联网下载(~100MB)。
离线开发设 `HF_HUB_OFFLINE=1` 环境变量(需先在线下载过一次到默认缓存)。

## 测试

- unit test:`pytest tests/adapters/embedding/ -v` — 全部 mock,不下载模型
- integration test:`RUN_EMBEDDING_INTEGRATION=1 pytest tests/adapters/embedding/test_sentence_transformer_integration.py -v` — 实地加载,需联网
