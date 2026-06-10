import { useRef } from "react";

interface UploadDropzoneProps {
  disabled: boolean;
  dragging: boolean;
  errorMessage?: string;
  onDragState: (dragging: boolean) => void;
  onFile: (file: File) => void;
}

export function UploadDropzone({
  disabled,
  dragging,
  errorMessage,
  onDragState,
  onFile,
}: UploadDropzoneProps) {
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
      className="upload-dropzone"
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
        accept=".zip,application/zip,application/x-zip-compressed"
        disabled={disabled}
        onChange={(event) => handleFiles(event.target.files)}
      />
      <span className="upload-dropzone__mark">ZIP</span>
      <strong>拖拽工程压缩包</strong>
      <span>或点击选择 .zip 文件</span>
      {errorMessage ? <p className="upload-dropzone__error">{errorMessage}</p> : null}
    </div>
  );
}
