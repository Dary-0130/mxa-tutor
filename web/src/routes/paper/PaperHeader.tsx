import { Link } from "react-router-dom";
import { resolveDocumentStatusErrorMessage } from "../../lib/errorMessages";
import type { PaperDomain, PaperSpec, PaperType, UploadDocumentStatus } from "../../lib/paperTypes";

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

function PaperPartialSuccessNotice({ documentStatuses }: { documentStatuses?: UploadDocumentStatus[] }) {
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
}: {
  spec: PaperSpec;
  documentStatuses?: UploadDocumentStatus[];
}) {
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
      </div>
      <Link className="paper-primary-link" to="/paper">
        重新上传
      </Link>
    </header>
  );
}
