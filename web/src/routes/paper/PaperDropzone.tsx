import { useRef } from "react";

interface PaperDropzoneProps {
  disabled: boolean;
  dragging: boolean;
  errorMessage?: string;
  onDragState: (dragging: boolean) => void;
  onFile: (file: File) => void;
}

export function PaperDropzone({
  disabled,
  dragging,
  errorMessage,
  onDragState,
  onFile,
}: PaperDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const openPicker = () => {
    if (!disabled) {
      inputRef.current?.click();
    }
  };

  const handleFiles = (files: FileList | null) => {
    const file = files?.item(0);
    if (file) {
      onFile(file);
    }
  };

  return (
    <div
      className="upload-dropzone paper-dropzone"
      data-dragging={dragging ? "true" : undefined}
      data-disabled={disabled ? "true" : undefined}
      role="button"
      tabIndex={disabled ? -1 : 0}
      onClick={openPicker}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openPicker();
        }
      }}
      onDragEnter={(event) => {
        event.preventDefault();
        onDragState(true);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        onDragState(true);
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        onDragState(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        onDragState(false);
        handleFiles(event.dataTransfer.files);
      }}
    >
      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        disabled={disabled}
        onChange={(event) => handleFiles(event.target.files)}
      />
      <span className="upload-dropzone__mark">PDF</span>
      <strong>上传论文文件</strong>
      <span>支持 PDF、Word(.pdf / .docx)</span>
      {errorMessage ? <p className="upload-dropzone__error">{errorMessage}</p> : null}
    </div>
  );
}
