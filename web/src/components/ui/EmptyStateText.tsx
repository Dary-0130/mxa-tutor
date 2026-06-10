interface EmptyStateTextProps {
  children: string;
}

export function EmptyStateText({ children }: EmptyStateTextProps) {
  return <p className="empty-state-text">{children}</p>;
}
