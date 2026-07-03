export const GLOBAL_ERROR_MESSAGES: Record<string, string> = {
  zip_bomb: "压缩文件异常,请检查后重新上传",
  zip_slip: "压缩包内含非法路径,请重新打包后上传",
  file_type_not_allowed: "工程包内包含暂不支持的文件类型",
  project_not_found: "找不到该工程,可能已过期或已被删除,请重新上传",
  project_too_large: "工程过大,请确认压缩包不超过 50MB,并减少无关文件后重试",
  upload_error: "上传文件有问题,请检查压缩包后重新上传",
  project_error: "工程处理失败,请重新上传后再试",
  document_too_large: "论文解析失败,请检查文件格式或稍后重试。",
  document_too_long_for_v0_1: "论文解析失败,请检查文件格式或稍后重试。",
  unsupported_document_format: "论文解析失败,请检查文件格式或稍后重试。",
  document_required: "请选择 PDF 或 DOCX 文件。",
  too_many_documents: "最多一次上传 5 篇资料。",
  document_parse_failed: "论文解析失败,请检查文件格式或稍后重试。",
  paper_spec_generation_failed: "资料理解失败,请稍后重试。",
  reparse_source_unavailable: "这份结果没有可重跑的临时文字,请重新上传",
  reparse_in_progress: "重新解析正在进行,请稍后。",
  regenerate_lock_conflict: "这份结果正在更新,请稍后重试。",
  regenerate_nothing_to_do: "当前步骤已经是完整的。",
  regenerate_store_failed: "步骤保存失败,旧结果已保留。",
  paper_user_supply_in_progress: "这份结果正在更新,请稍后重试。",
  correction_target_not_extracted: "这个参数不能直接纠错,请刷新后重试。",
  correction_requires_local_rerun: "这个参数需要局部重跑后才能处理。",
  correction_target_ambiguous: "这个参数暂时不能唯一定位,请刷新后重试。",
  correction_target_stale: "参数状态已变化,请刷新后重试。",
  correction_target_not_correctable: "这个参数不能在这里纠错。",
  correction_invalid_value: "纠错值无效,请重新输入。",
  correction_unit_invalid: "单位无效,请重新输入。",
  correction_lock_conflict: "这份结果正在更新,请稍后重试。",
  correction_not_found: "这条纠错记录不存在或已失效。",
  correction_store_failed: "纠错保存失败,旧结果已保留。",
  paper_reparse_failed: "重新解析失败,旧结果已保留。",
  paper_reparse_store_failed: "重新解析保存失败,旧结果已保留。",
  document_processing_failed: "资料处理失败,请重新上传后再试。",
  paper_not_found: "论文结果不存在或已过期,请重新上传。",
  internal_error: "出了点问题,我们已经记录,稍后再试",
  llm_auth: "服务暂时不可用,请稍后重试",
  llm_quota: "服务繁忙,请稍后",
  llm_rate_limit: "请求太频繁,稍等一下",
  llm_timeout: "网络较慢,正在重试...",
  llm_server: "AI 服务暂不稳定,请刷新重试",
  slx_parse: "Simulink 模型解析失败,可能版本过老或损坏",
  m_parse: ".m 文件解析失败,请检查文件编码",
  parse_error: "工程解析失败,请检查 Simulink 或 .m 文件是否完整后重试",
  overview_generation: "导览生成失败,请刷新重试",
  chat_session_not_found: "对话不存在",
  store_error: "系统暂时不可用,请稍后重试",
  chat_generation: "回答生成失败,请刷新重试",
  quota_exhausted: "已达到合理使用上限,可联系加量",
  evidence_missing: "出了点问题,我们已经记录,稍后再试",
  not_found: "请求的资源不存在",
  validation_error: "请求参数有问题,请检查后重试",
  method_not_allowed: "请求方式不支持",
  http_error: "请求失败,请稍后重试",
  embedding_model_load: "AI 智能解析服务暂时不可用,请稍后重试",
  parse_timeout: "解析时间超过 2 分钟,工程可能过大或服务繁忙,请稍后重试",
  network_error: "网络连接失败,请检查网络后重试",
};

export const DOCUMENT_STATUS_ERROR_MESSAGES: Record<string, string> = {
  document_parse_failed: "文件内容未能读取(可能格式不支持、体量过大或文件损坏)。",
  paper_spec_generation_failed: "文件已读取,但未能从中提取出结构化内容。",
  document_processing_failed: "该文件未能处理成功。",
};

export function resolveErrorMessage(code: string | undefined): string {
  if (!code) {
    return "出了点问题,请稍后再试";
  }
  return GLOBAL_ERROR_MESSAGES[code] ?? "出了点问题,请稍后再试";
}

export function resolveDocumentStatusErrorMessage(code: string | null | undefined): string {
  if (!code) {
    return "该文件未能读取成功。";
  }
  return DOCUMENT_STATUS_ERROR_MESSAGES[code] ?? "该文件未能读取成功。";
}
