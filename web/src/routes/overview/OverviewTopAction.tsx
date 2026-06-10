import { Link } from "react-router-dom";

interface OverviewTopActionProps {
  projectId: string;
  seen: boolean;
  onJumpToEnd: () => void;
}

export function OverviewTopAction({ projectId, seen, onJumpToEnd }: OverviewTopActionProps) {
  return (
    <div className="overview-top-action">
      {seen ? (
        <Link to={`/view/${projectId}/chat`}>继续提问</Link>
      ) : (
        <button type="button" onClick={onJumpToEnd}>
          跳到末屏
        </button>
      )}
    </div>
  );
}
