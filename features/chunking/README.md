# Chunking

`features/chunking` turns parsed project structures and generated overviews into
embeddable records for the vector store.

- Project entry: 5 类 project chunks: `m_file`, `m_function`, `slx_block`,
  `slx_subsystem`, `mat_variable`
- Overview entry: `project_overview`
- `teaching_unit` is reserved and is not emitted in this task

The module depends on domain models, interfaces, settings, and the public
overview schema only.
