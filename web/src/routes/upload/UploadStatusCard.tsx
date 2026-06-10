interface UploadStatusCardProps {
  file: File;
  phase: "uploading" | "parsing";
  progress: number;
  onCancel?: () => void;
}

function formatBytes(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(mb >= 10 ? 1 : 2)} MB`;
}

export function UploadStatusCard({ file, phase, progress, onCancel }: UploadStatusCardProps) {
  const percent = phase === "parsing" ? 100 : Math.max(0, Math.min(100, progress));
  return (
    <section className="upload-status-card" aria-live="polite">
      <div>
        <h2>{file.name}</h2>
        <p>{formatBytes(file.size)}</p>
      </div>
      <div className="upload-status-card__row">
        <span>{phase === "uploading" ? "上传中" : "解析中"}</span>
        <span>{phase === "uploading" ? `${Math.round(percent)}%` : "请稍候"}</span>
      </div>
      <div className="upload-progress" aria-hidden="true">
        <span style={{ width: `${percent}%` }} />
      </div>
      {phase === "uploading" && onCancel ? (
        <button className="text-command" type="button" onClick={onCancel}>
          取消上传
        </button>
      ) : null}
    </section>
  );
}
