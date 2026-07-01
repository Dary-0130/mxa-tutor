import type { UploadSubmissionItem } from "./paperUploadLogic";

export interface PaperUploadQueueItem extends UploadSubmissionItem<File> {
  fingerprint: string;
  validationMessage?: string;
}

interface PaperUploadQueueProps {
  items: PaperUploadQueueItem[];
  primaryLocalId: string | null;
  locked: boolean;
  canSubmit: boolean;
  errorMessage?: string;
  noticeMessage?: string;
  onRemove: (localId: string) => void;
  onTogglePrimary: (localId: string) => void;
  onSubmit: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (bytes >= 1024) {
    return `${Math.ceil(bytes / 1024)} KB`;
  }
  return `${bytes} B`;
}

export function PaperUploadQueue({
  items,
  primaryLocalId,
  locked,
  canSubmit,
  errorMessage,
  noticeMessage,
  onRemove,
  onTogglePrimary,
  onSubmit,
}: PaperUploadQueueProps) {
  const validCount = items.filter((item) => item.validation === "valid").length;
  const invalidCount = items.length - validCount;
  const showPrimaryControls = validCount > 1;

  return (
    <section className="paper-upload-queue paper-readable-card" aria-label="待生成资料">
      <div className="paper-upload-queue__head">
        <div>
          <p className="section-kicker">SELECTED</p>
          <h2>待生成资料</h2>
        </div>
        <span>
          {validCount} 可用{invalidCount > 0 ? ` / ${invalidCount} 不可用` : ""}
        </span>
      </div>
      {noticeMessage ? <p className="paper-upload-queue__notice">{noticeMessage}</p> : null}
      {errorMessage ? <p className="paper-upload-queue__error">{errorMessage}</p> : null}
      <ul className="paper-upload-queue__list">
        {items.map((item) => {
          const isPrimary = primaryLocalId === item.localId;
          const isValid = item.validation === "valid";
          return (
            <li
              className="paper-upload-queue__item"
              data-invalid={isValid ? undefined : "true"}
              data-primary={isPrimary ? "true" : undefined}
              key={item.localId}
            >
              <div className="paper-upload-queue__file">
                <strong>{item.file.name}</strong>
                <span>{formatFileSize(item.file.size)}</span>
                {isValid ? null : <p>{item.validationMessage ?? "该文件暂不可用。"}</p>}
              </div>
              <div className="paper-upload-queue__actions">
                {showPrimaryControls && isValid ? (
                  <button
                    type="button"
                    className="paper-primary-toggle"
                    aria-pressed={isPrimary}
                    aria-label={isPrimary ? `取消 ${item.file.name} 的主文献标记` : `将 ${item.file.name} 设为主文献`}
                    disabled={locked}
                    onClick={() => onTogglePrimary(item.localId)}
                  >
                    {isPrimary ? "主文献" : "设为主"}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="paper-icon-button"
                  aria-label={`移除 ${item.file.name}`}
                  disabled={locked}
                  onClick={() => onRemove(item.localId)}
                >
                  ×
                </button>
              </div>
            </li>
          );
        })}
      </ul>
      {showPrimaryControls ? (
        <p className="paper-upload-queue__hint">主文献只决定生成时的主次身份,不代表内容更可信。</p>
      ) : null}
      <div className="paper-upload-queue__footer">
        <button
          type="button"
          className="paper-primary-button"
          disabled={locked || !canSubmit}
          onClick={onSubmit}
        >
          {locked ? "生成中" : "开始生成"}
        </button>
      </div>
    </section>
  );
}
