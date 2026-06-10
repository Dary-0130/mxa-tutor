import { useEffect, useState, type RefObject } from "react";

const PANORAMA_WIDTH = 3840;

export function useParallaxBg(scrollRef: RefObject<HTMLElement | null>, panelCount: number) {
  const [panoramaX, setPanoramaX] = useState(0);

  useEffect(() => {
    const root = scrollRef.current;
    if (!root) {
      return undefined;
    }

    let frame = 0;
    const update = () => {
      const viewport = window.innerWidth;
      const totalScrollable = Math.max(1, (panelCount - 1) * viewport);
      const maxBgOffset = Math.max(0, PANORAMA_WIDTH - viewport);
      const progress = Math.min(1, Math.max(0, root.scrollLeft / totalScrollable));
      setPanoramaX(-maxBgOffset * progress);
    };

    const requestUpdate = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(update);
    };

    update();
    root.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);
    return () => {
      window.cancelAnimationFrame(frame);
      root.removeEventListener("scroll", requestUpdate);
      window.removeEventListener("resize", requestUpdate);
    };
  }, [panelCount, scrollRef]);

  return panoramaX;
}
