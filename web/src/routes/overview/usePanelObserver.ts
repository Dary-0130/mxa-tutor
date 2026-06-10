import { useEffect, useState, type RefObject } from "react";

export function usePanelObserver(
  scrollRef: RefObject<HTMLElement | null>,
  onPanelVisible?: (index: number) => void,
) {
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    const root = scrollRef.current;
    if (!root) {
      return undefined;
    }

    const panels = Array.from(root.querySelectorAll<HTMLElement>(".overview-panel"));
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.6)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) {
          return;
        }
        const index = Number((visible.target as HTMLElement).dataset.panelIndex ?? 0);
        setCurrentIndex(index);
        onPanelVisible?.(index);
      },
      { root, threshold: 0.6 },
    );

    panels.forEach((panel) => observer.observe(panel));
    return () => observer.disconnect();
  }, [onPanelVisible, scrollRef]);

  return currentIndex;
}
