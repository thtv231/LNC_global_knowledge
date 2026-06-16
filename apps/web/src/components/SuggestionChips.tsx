interface Props {
  suggestions: string[];
  onSelect: (q: string) => void;
  disabled: boolean;
}

export function SuggestionChips({ suggestions, onSelect, disabled }: Props) {
  if (!suggestions?.length) return null;

  return (
    <div className="mt-3 pt-2.5 border-t border-gray-100 dark:border-gray-700">
      <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-2">
        Câu hỏi tiếp theo
      </p>
      <div className="flex flex-col gap-1.5">
        {suggestions.map((s, i) => (
          <button
            key={i}
            onClick={() => !disabled && onSelect(s)}
            disabled={disabled}
            className="text-left text-xs px-3 py-2 rounded-xl
                       border border-gray-200 dark:border-gray-700
                       bg-gray-50 dark:bg-gray-800/60
                       text-gray-700 dark:text-gray-300
                       hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20
                       hover:text-blue-700 dark:hover:text-blue-300
                       disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all duration-150 group"
          >
            <span className="text-blue-400 mr-1.5 group-hover:text-blue-600">→</span>{s}
          </button>
        ))}
      </div>
    </div>
  );
}
