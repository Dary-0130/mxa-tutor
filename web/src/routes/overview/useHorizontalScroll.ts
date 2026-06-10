import { useCallback, useEffect, type RefObject } from "react";

function targetIsScrollable(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest("[data-native-scroll]") !== null;
}

function shouldLetNativeScroll(target: EventTarget | null, deltaY: number): boolean {
  if (!(target instanceof Element)) {
    return false;
  }
  const scrollable = target.closest("[data-native-scroll]") as HTMLElement | null;
  if (!scrollable) {
    return false;
  }
  const atTop = scrollable.scrollTop === 0;
  const atBottom = scrollable.scrollTop + scrollable.clientHeight >= scrollable.scrollHeight - 1;
  return (deltaY < 0 && !atTop) || (deltaY > 0 && !atBottom);
}

export function useHorizontalScroll(scrollRef: RefObject<HTMLElement | null>, panelCount: number) {
  const scrollToPanel = useCallback(
    (index: number, behavior: ScrollBehavior = "smooth") => {
      const root = scrollRef.current;
      if (!root) {
        return;
      }
      const next = Math.max(0, Math.min(panelCount - 1, index));
      root.scrollTo({ left: next * window.innerWidth, behavior });
    },
    [panelCount, scrollRef],
  );

  useEffect(() => {
    const root = scrollRef.current;
    if (!root) {
      return undefined;
    }

    const currentPanel = () => Math.round(root.scrollLeft / window.innerWidth);

    const onWheel = (event: WheelEvent) => {
      if (Math.abs(event.deltaX) >= Math.abs(event.deltaY)) {
        return;
      }
      if (shouldLetNativeScroll(event.target, event.deltaY)) {
        return;
      }
      event.preventDefault();
      root.scrollLeft += event.deltaY;
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const current = currentPanel();
      switch (event.key) {
        case "ArrowRight":
        case "PageDown":
          event.preventDefault();
          scrollToPanel(current + 1);
          break;
        case "ArrowLeft":
        case "PageUp":
          event.preventDefault();
          scrollToPanel(current - 1);
          break;
        case "Home":
          event.preventDefault();
          scrollToPanel(0);
          break;
        case "End":
          event.preventDefault();
          scrollToPanel(panelCount - 1);
          break;
        case "ArrowDown":
        case "ArrowUp":
          if (!targetIsScrollable(event.target)) {
            event.preventDefault();
            scrollToPanel(current + (event.key === "ArrowDown" ? 1 : -1));
          }
          break;
      }
    };

    root.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKeyDown);
    return () => {
      root.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [panelCount, scrollRef, scrollToPanel]);

  return scrollToPanel;
}
