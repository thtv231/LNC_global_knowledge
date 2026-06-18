import { useEffect, useState } from 'react';

const STEPS = [
  { id: 1, label: 'Đọc & parse CV',               est: '2s'  },
  { id: 2, label: 'Trích xuất thông tin hồ sơ',    est: '5s'  },
  { id: 3, label: 'Tính điểm EB-1A / EB-2 NIW',    est: '1s'  },
  { id: 4, label: 'So sánh với approved cases',     est: '2s'  },
  { id: 5, label: 'Sinh báo cáo Gap Analysis (AI)', est: '30s' },
];

const STEP_DURATION = [2000, 5000, 1000, 2000, 30000];

export function CVAnalyzingCardAuto({ onDone }: { onDone?: () => void }) {
  const [step, setStep] = useState(1);

  useEffect(() => {
    if (step > STEPS.length) { onDone?.(); return; }
    const t = setTimeout(() => setStep(s => s + 1), STEP_DURATION[step - 1] ?? 900);
    return () => clearTimeout(t);
  }, [step, onDone]);

  const progress = Math.min(((step - 1) / STEPS.length) * 100, 100);

  return (
    <div className="flex justify-start mb-4 gap-2.5 items-start msg-enter">
      {/* Avatar */}
      <div className="w-8 h-8 rounded-md flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-semibold tracking-wide"
        style={{ background: 'var(--navy-deep)', color: 'var(--gold)', border: '1px solid var(--navy-mid)' }}>
        L&C
      </div>

      <div className="rounded-2xl rounded-tl-sm px-5 py-4 w-[300px]"
        style={{ background: '#FFFFFF', border: '1px solid var(--border-main)' }}>

        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <svg className="animate-spin w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none"
              style={{ color: 'var(--gold)' }}>
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
            </svg>
            <span className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
              Đang phân tích hồ sơ...
            </span>
          </div>
          <span className="text-[11px] font-semibold tabular-nums" style={{ color: 'var(--gold)' }}>
            {Math.round(progress)}%
          </span>
        </div>

        {/* Progress bar */}
        <div className="h-1 rounded-full mb-4 overflow-hidden"
          style={{ background: 'var(--border-main)' }}>
          <div className="h-full rounded-full transition-all duration-700 ease-out"
            style={{ width: `${progress}%`, background: 'var(--gold)' }} />
        </div>

        {/* Steps */}
        <div className="space-y-2.5">
          {STEPS.map(s => {
            const isDone   = s.id < step;
            const isActive = s.id === step;
            return (
              <div key={s.id}
                className="flex items-center gap-2.5 transition-all duration-300"
                style={{ opacity: isDone ? 0.45 : isActive ? 1 : 0.28 }}>

                {/* Step dot */}
                <div className="w-[18px] h-[18px] rounded-full flex items-center justify-center shrink-0 transition-all duration-300"
                  style={{
                    background: isDone ? 'var(--risk-ok)' : isActive ? 'var(--gold-light)' : 'transparent',
                    border: isDone ? 'none' : isActive ? '1.5px solid var(--gold)' : '1.5px solid var(--border-soft)',
                  }}>
                  {isDone ? (
                    <svg width="9" height="9" viewBox="0 0 12 12" fill="none"
                      stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="2 6 5 9 10 3"/>
                    </svg>
                  ) : isActive ? (
                    <span className="w-[6px] h-[6px] rounded-full animate-pulse"
                      style={{ background: 'var(--gold)' }} />
                  ) : null}
                </div>

                <span className="text-[12px] flex-1 leading-tight"
                  style={{ color: isActive ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: isActive ? 500 : 400 }}>
                  {s.label}
                </span>

                {isActive && (
                  <span className="text-[10px] font-medium shrink-0" style={{ color: 'var(--gold)' }}>
                    ~{s.est}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        <p className="text-[11px] mt-3.5 pt-3" style={{ color: 'var(--text-faint)', borderTop: '1px solid var(--border-main)' }}>
          Tổng thời gian dự kiến: ~40–60 giây
        </p>
      </div>
    </div>
  );
}
