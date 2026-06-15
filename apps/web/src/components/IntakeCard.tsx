import { useState } from 'react';
import type { IntakeOption } from '../types/chat';

interface Props {
  options: IntakeOption[];
  onSelect: (value: string) => void;
  disabled: boolean;
  title?: string;
  variant?: 'program' | 'profile';
}

export function IntakeCard({ options, onSelect, disabled, title, variant = 'program' }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [inputText, setInputText] = useState('');

  if (!options?.length) return null;

  const isProfile = variant === 'profile';
  const accentColor = isProfile ? '#2D9E34' : '#0C3656';
  const hoverBorder = isProfile ? 'hover:border-green-500' : 'hover:border-[#0C3656]';
  const hoverBg    = isProfile ? 'hover:bg-green-50 dark:hover:bg-green-900/20' : 'hover:bg-blue-50 dark:hover:bg-blue-900/20';
  const baseBorder = isProfile ? 'border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-900/10' : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800';
  const numBase   = isProfile ? 'bg-green-100 text-green-700' : 'bg-gray-100 dark:bg-gray-700 text-gray-500';

  const handleClick = (opt: IntakeOption, i: number) => {
    if (opt.value.includes('___')) {
      setExpandedIdx(i);
      setInputText(opt.value);
    } else {
      onSelect(opt.value);
    }
  };

  const handleSend = () => {
    const text = inputText.trim();
    if (!text) return;
    onSelect(text);
    setExpandedIdx(null);
    setInputText('');
  };

  return (
    <div className="mt-3 pt-2.5 border-t border-gray-100 dark:border-gray-700 space-y-1.5">
      <p className="text-[11px] font-semibold uppercase tracking-wide mb-2"
        style={{ color: accentColor }}>
        {title ?? (isProfile ? 'Chia sẻ profile để tư vấn chính xác hơn' : 'Anh/Chị muốn tìm hiểu về')}
      </p>

      {options.map((opt, i) => {
        const isInput = opt.value.includes('___');
        const isExpanded = expandedIdx === i;

        if (isExpanded) {
          return (
            <div key={i} className={`rounded-xl border p-3 space-y-2 ${baseBorder}`}
              style={{ borderColor: accentColor }}>
              <p className="text-xs font-medium" style={{ color: accentColor }}>{opt.label}</p>
              <textarea
                autoFocus
                rows={4}
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                className="w-full text-xs rounded-lg border border-gray-200 dark:border-gray-600
                           bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300
                           px-3 py-2 outline-none resize-none
                           focus:ring-2 focus:border-transparent"
                style={{ '--tw-ring-color': accentColor } as React.CSSProperties}
                onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) handleSend(); }}
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => { setExpandedIdx(null); setInputText(''); }}
                  className="px-3 py-1.5 text-xs rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors">
                  Huỷ
                </button>
                <button
                  onClick={handleSend}
                  disabled={!inputText.trim() || disabled}
                  className="px-3 py-1.5 text-xs rounded-lg text-white font-semibold transition-colors disabled:opacity-40"
                  style={{ backgroundColor: accentColor }}>
                  Gửi →
                </button>
              </div>
              <p className="text-[10px] text-gray-400">Điền vào chỗ ___ rồi nhấn Gửi hoặc Ctrl+Enter</p>
            </div>
          );
        }

        return (
          <button
            key={i}
            onClick={() => handleClick(opt, i)}
            disabled={disabled}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border
                       text-left text-sm transition-all duration-150 group
                       disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-sm
                       ${baseBorder} ${hoverBorder} ${hoverBg}
                       ${isInput ? 'border-dashed' : ''}`}
          >
            <span className={`shrink-0 w-6 h-6 rounded-full text-xs flex items-center justify-center
                             font-semibold transition-colors ${numBase}`}
              style={{} as React.CSSProperties}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = accentColor; (e.currentTarget as HTMLElement).style.color = 'white'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = ''; (e.currentTarget as HTMLElement).style.color = ''; }}>
              {i + 1}
            </span>
            <span className="flex-1 text-gray-700 dark:text-gray-300 transition-colors">
              {opt.label}
            </span>
            <span className="text-gray-300 transition-colors text-base">
              {isInput ? '✏️' : '→'}
            </span>
          </button>
        );
      })}
    </div>
  );
}
