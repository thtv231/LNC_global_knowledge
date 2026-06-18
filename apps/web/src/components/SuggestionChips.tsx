interface Props {
  suggestions: string[];
  onSelect: (q: string) => void;
  disabled: boolean;
}

export function SuggestionChips({ suggestions, onSelect, disabled }: Props) {
  if (!suggestions?.length) return null;

  return (
    <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--c-border)' }}>
      <p className="text-[10px] font-semibold uppercase tracking-widest mb-2" style={{ color: 'var(--c-text-3)' }}>
        Câu hỏi tiếp theo
      </p>
      <div className="flex flex-col gap-1.5">
        {suggestions.map((s, i) => (
          <button key={i} onClick={() => !disabled && onSelect(s)} disabled={disabled}
            className="text-left text-xs px-3 py-2 rounded-lg transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ border: '1px solid var(--c-border)', background: 'var(--c-surface)', color: 'var(--c-text-2)' }}
            onMouseEnter={e => {
              if (disabled) return;
              const el = e.currentTarget as HTMLButtonElement;
              el.style.borderColor = 'var(--c-blue)';
              el.style.color = 'var(--c-blue)';
              el.style.background = '#EFF6FF';
            }}
            onMouseLeave={e => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.borderColor = 'var(--c-border)';
              el.style.color = 'var(--c-text-2)';
              el.style.background = 'var(--c-surface)';
            }}>
            <span className="font-semibold mr-1.5" style={{ color: 'var(--c-blue)' }}>→</span>{s}
          </button>
        ))}
      </div>
    </div>
  );
}
