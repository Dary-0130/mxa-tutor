interface FileRowProps {
  path: string;
  note: string;
}

export function FileRow({ path, note }: FileRowProps) {
  return (
    <article className="file-row">
      <strong>{path}</strong>
      <span>{note}</span>
    </article>
  );
}
