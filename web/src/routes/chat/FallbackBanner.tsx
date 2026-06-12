interface FallbackBannerProps {
  show: boolean;
}

export function FallbackBanner({ show }: FallbackBannerProps) {
  if (!show) {
    return null;
  }
  return (
    <div className="mt-4 border-l-2 border-[var(--color-signal)] pl-3 text-sm text-[var(--color-signal-dim)]">
      [证据不足] 以下回答仅供参考
    </div>
  );
}
