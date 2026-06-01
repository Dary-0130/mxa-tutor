# core/domain

核心层领域数据结构,只描述业务概念本身,不包含解析、存储、LLM 调用等行为。

- `source_ref.py`: 证据引用结构,用于把讲解和问答锚定到文件、行号或 block。
- `project.py`: 上传工程、工程文件元信息和工程类型枚举。
- `slx_model.py`: `.slx` 模型解析后的 block、line、model 结构。
- `m_file.py`: `.m` 文件解析后的函数和文件结构。
- `mat_metadata.py`: `.mat` 文件变量元信息,不存原始数据。
- `project_graph.py`: 工程结构理解图的节点、边、图和类型枚举。
- `teaching_unit.py`: 面向讲解生成的教学单元结构。
- `exceptions.py`: 业务异常基类及 LLM、解析、工程、上传、额度、证据异常。

详见 `docs/02_ARCHITECTURE_OVERVIEW.md` 第 3 节和第 4 节。
