# core/interfaces

核心层抽象接口,定义功能层依赖的能力契约,具体实现放在 adapters 层。

- `llm_provider.py`: 文本 LLM 提供方接口以及消息、响应、模型能力数据结构。
- `embedder.py`: 嵌入模型接口,提供批量向量化和维度声明。
- `parser.py`: `.slx` 与 `.m` 文件解析器接口。
- `matlab_engine_provider.py`: 服务层可见的 MATLAB Engine 健康检查窄接口。

详见 `docs/02_ARCHITECTURE_OVERVIEW.md` 第 3 节和第 4 节。
