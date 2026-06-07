# features/chat

ChatService 智能问答。

## Retrievers

`KeywordRetriever` 提供基于文件名、函数名、block 名和 ProjectGraph 元数据的粗检索。

`VectorRetriever` 使用 `EmbeddingProvider` 生成问题向量,再通过 `VectorStore`
查询项目 chunks,并把 `m_file / m_function / slx_block / slx_subsystem /
mat_variable / project_overview` 映射为 ChatService 使用的 `RetrievalHit`。

`HybridRetriever` 是当前线上装配入口:当项目 chunks 未就绪、向量存储不可用、
embedding 失败或向量召回为空时,用结构化 `fallback_reason` 记录元数据后降级到
`KeywordRetriever`。它不改变 `ChatService.handle_chat` 的流程。

详见 `docs/02_ARCHITECTURE_OVERVIEW.md` 第 3 节。
