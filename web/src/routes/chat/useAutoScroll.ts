import { useCallback, useEffect, useRef, useState } from "react";

export function useAutoScroll(dependency: unknown) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [lockedToBottom, setLockedToBottom] = useState(true);

  const handleScroll = useCallback(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }
    const distanceFromBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
    setLockedToBottom(distanceFromBottom < 120);
  }, []);

  useEffect(() => {
    if (!lockedToBottom) {
      return;
    }
    const element = containerRef.current;
    if (!element) {
      return;
    }
    element.scrollTop = element.scrollHeight;
  }, [dependency, lockedToBottom]);

  return { containerRef, handleScroll, lockedToBottom };
}
