interface PanelIndicatorProps {
  currentIndex: number;
  total: number;
  onSelect: (index: number) => void;
}

export function PanelIndicator({ currentIndex, total, onSelect }: PanelIndicatorProps) {
  return (
    <nav className="panel-indicator" aria-label="导览屏幕" role="navigation">
      {Array.from({ length: total }, (_, index) => (
        <button
          key={index}
          type="button"
          data-active={currentIndex === index ? "true" : undefined}
          aria-current={currentIndex === index ? "step" : undefined}
          onClick={() => onSelect(index)}
        >
          {String(index + 1).padStart(2, "0")}
        </button>
      ))}
    </nav>
  );
}
