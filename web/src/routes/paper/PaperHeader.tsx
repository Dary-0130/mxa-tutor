import { useState } from "react";
import { Link } from "react-router-dom";
import type { ApiException } from "../../lib/api";
import { resolveDocumentStatusErrorMessage, resolveErrorMessage } from "../../lib/errorMessages";
import type { PaperDomain, PaperSpec, PaperType, UploadDocumentStatus } from "../../lib/paperTypes";

const REPARSE_CONFIRM_COPY = {
  prefix: "重新解析会用同一份论文文字重新抽取并",
  currentResult: "替换当前结果",
  separator: ";",
  resetScope: "已补充的缺失参数、当前 plan 和调参结果会被替换,已纠错的参数值也会被替换",
  suffix:
    "。它只重跑已读入的论文文字;若缺的信息在图片 / 表格里,或某篇上传时就失败,重新解析补不回,需要重新上传或等解析升级。",
};

const DOMAIN_LABELS: Record<PaperDomain, string> = {
  control_system: "控制系统",
  signal_processing: "信号处理",
  power_electronics: "电力电子",
  communication: "通信",
  motor_control: "电机控制",
  new_energy: "新能源",
};

const PAPER_TYPE_LABELS: Record<PaperType, string> = {
  paper: "论文",
  report: "报告",
  thesis: "学位论文",
};

function shouldShowDocumentSources(
  spec: PaperSpec,
  documentStatuses: UploadDocumentStatus[] | undefined,
): boolean {
  const originalDocumentCount = documentStatuses?.length ?? spec.documents.length;
  return originalDocumentCount > 1 || spec.documents.length > 1;
}

function PaperPartialSuccessNotice({
  documentStatuses,
}: {
  documentStatuses?: UploadDocumentStatus[];
}) {
  const failedStatuses = documentStatuses?.filter((status) => status.status === "failed") ?? [];
  if (!documentStatuses || failedStatuses.length === 0) {
    return null;
  }
  const totalCount = documentStatuses.length;
  const failedCount = failedStatuses.length;
  return (
    <aside className="paper-partial-notice" aria-label="部分资料未读取成功">
      <p>
        共 {totalCount} 篇资料,{failedCount} 篇未读取成功。系统已基于读取成功的{" "}
        {totalCount - failedCount} 篇生成结果。
      </p>
      <div>
        <strong>未读取成功</strong>
        <ul>
          {failedStatuses.map((status) => (
            <li key={status.document_id}>
              <span>{status.filename}</span>
              <small>{resolveDocumentStatusErrorMessage(status.error_code)}</small>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

function PaperDocumentSources({
  spec,
  documentStatuses,
}: {
  spec: PaperSpec;
  documentStatuses?: UploadDocumentStatus[];
}) {
  if (!shouldShowDocumentSources(spec, documentStatuses)) {
    return null;
  }
  const totalCount = documentStatuses?.length ?? spec.documents.length;
  return (
    <div className="paper-document-sources" aria-label="资料来源">
      <div className="paper-document-sources__summary">
        <strong>
          已读取 {spec.documents.length}/{totalCount} 篇资料
        </strong>
      </div>
      <ul>
        {spec.documents.map((document) => (
          <li key={document.document_id}>
            <span>{document.filename}</span>
            {document.document_id === spec.primary_document_id ? <small>主文献</small> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PaperHeader({
  spec,
  documentStatuses,
  onReparse,
  onDismissReparseError,
  reparsing,
  reparseError,
  reparseSourceUnavailable,
}: {
  spec: PaperSpec;
  documentStatuses?: UploadDocumentStatus[];
  onReparse: () => void;
  onDismissReparseError: () => void;
  reparsing: boolean;
  reparseError: ApiException | null;
  reparseSourceUnavailable: boolean;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const sourceUnavailable =
    reparseSourceUnavailable || reparseError?.code === "reparse_source_unavailable";
  const sourceUnavailableMessage = "这份结果没有可重跑的临时文字,请重新上传";
  const reparseMessage =
    !sourceUnavailable && reparseError ? resolveErrorMessage(reparseError.code) : "";

  function confirmReparse() {
    setConfirmOpen(false);
    onReparse();
  }

  return (
    <header className="paper-header">
      <div>
        <p className="section-kicker">PAPER WORKBENCH</p>
        <h1>{spec.paper_title}</h1>
        <p className="paper-copy">{spec.abstract}</p>
        <div className="paper-header__tags" aria-label="论文元信息">
          <span>{DOMAIN_LABELS[spec.domain]}</span>
          <span>{PAPER_TYPE_LABELS[spec.paper_type]}</span>
        </div>
        <PaperPartialSuccessNotice documentStatuses={documentStatuses} />
        <PaperDocumentSources spec={spec} documentStatuses={documentStatuses} />
        {reparseMessage ? (
          <aside className="paper-reparse-notice" aria-live="polite">
            <span>{reparseMessage}</span>
            {!sourceUnavailable ? (
              <button type="button" onClick={onDismissReparseError}>
                关闭
              </button>
            ) : null}
          </aside>
        ) : null}
      </div>
      <div className="paper-header__actions">
        <button
          className="paper-secondary-button"
          type="button"
          disabled={reparsing || sourceUnavailable}
          onClick={() => setConfirmOpen(true)}
        >
          {reparsing ? "重新解析中" : "重新解析"}
        </button>
        <Link className="paper-primary-link" to="/paper">
          重新上传
        </Link>
        {sourceUnavailable ? (
          <span className="paper-reparse-action-hint">{sourceUnavailableMessage}</span>
        ) : null}
      </div>
      {confirmOpen ? (
        <dialog className="paper-reparse-dialog" open>
          <form method="dialog">
            <h2>重新解析</h2>
            <p>
              {REPARSE_CONFIRM_COPY.prefix}
              <strong>{REPARSE_CONFIRM_COPY.currentResult}</strong>
              {REPARSE_CONFIRM_COPY.separator}
              <strong>{REPARSE_CONFIRM_COPY.resetScope}</strong>
              {REPARSE_CONFIRM_COPY.suffix}
            </p>
            <div>
              <button
                type="button"
                className="paper-secondary-button"
                onClick={() => setConfirmOpen(false)}
              >
                取消
              </button>
              <button
                type="button"
                className="paper-primary-button"
                disabled={reparsing}
                onClick={confirmReparse}
              >
                确认重新解析
              </button>
            </div>
          </form>
        </dialog>
      ) : null}
    </header>
  );
}
