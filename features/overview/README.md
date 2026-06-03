# features/overview

`features/overview/` 承载项目导览相关的内部构建逻辑。

本 Task 首次加入 `ProjectGraphBuilder`,它把上游 parser 产物
(`Project.m_files` / `Project.slx_models` / `Project.mat_files` /
`Project.file_dependencies`)转换为 `ProjectGraph`。

职责边界:

- 不调用 LLM
- 不重新扫描 `MFile.raw_code`
- 不执行任何用户上传代码
- `data_flow` / `control_flow` 在 v0.1 保持空列表

用法示例:

```python
from features.overview import ProjectGraphBuilder

builder = ProjectGraphBuilder()
graph = builder.build(project)

print(len(graph.nodes))
print(graph.entry_points)
```
