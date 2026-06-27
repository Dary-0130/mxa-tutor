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
  document_parse_failed: "论文解析失败,请检查文件格式或稍后重试。",
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

export function resolveErrorMessage(code: string | undefined): string {
  if (!code) {
    return "出了点问题,请稍后再试";
  }
  return GLOBAL_ERROR_MESSAGES[code] ?? `出了点问题(${code}),请稍后再试`;
}
