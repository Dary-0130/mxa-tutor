interface FollowUpChipsProps {
  suggestions?: string[];
  onSelect: (value: string) => void;
}

export function FollowUpChips({ suggestions, onSelect }: FollowUpChipsProps) {
  const visibleSuggestions = suggestions?.slice(0, 3) ?? [];
  if (visibleSuggestions.length === 0) {
    return null;
  }
  return (
    <div className="mt-4 flex flex-wrap gap-2">
      {visibleSuggestions.map((suggestion) => (
        <button
          className="border border-[var(--color-rebar)] px-3 py-2 text-left text-xs text-[var(--color-ite)] hover:border-[var(--color-signal)] focus:outline-2 focus:outline-[var(--color-signal)]"
          key={suggestion}
          type="button"
          onClick={() => onSelect(suggestion)}
        >
          {suggestion}
        </button>
      ))}
    </div>
  );
}
