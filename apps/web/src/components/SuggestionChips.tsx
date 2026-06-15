interface Props {
  suggestions: string[];
  onSelect: (q: string) => void;
  disabled: boolean;
}

export function SuggestionChips({ suggestions, onSelect, disabled }: Props) {
  if (!suggestions?.length) return null;

  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {suggestions.map((s, i) => (
        <button
          key={i}
          onClick={() => !disabled && onSelect(s)}
          disabled={disabled}
          className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-gray-600
                     text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700
                     disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {s}
        </button>
      ))}
    </div>
  );
}
