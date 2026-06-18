interface Props { name: string; size: number; }

export function CVFileBubble({ name, size }: Props) {
  const kb = size / 1024;
  const sizeStr = kb > 1024 ? (kb / 1024).toFixed(1) + ' MB' : Math.round(kb) + ' KB';
  const isPDF = name.toLowerCase().endsWith('.pdf');

  return (
    <div className="flex justify-end mb-4 gap-2.5 items-end msg-enter">
      <div className="flex items-center gap-3 rounded-2xl rounded-br-sm px-3.5 py-3 max-w-[260px]"
        style={{ background: 'var(--border-soft)', border: '1px solid var(--border-main)' }}>

        {/* File type badge */}
        <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: '#FFFFFF', border: '1px solid var(--border-main)' }}>
          <svg width="18" height="20" viewBox="0 0 20 22" fill="none">
            <rect x="1" y="1" width="14" height="20" rx="2"
              stroke="var(--text-muted)" strokeWidth="1.5"/>
            <polyline points="5 1 5 6 1 6"
              stroke="var(--text-muted)" strokeWidth="1.5" strokeLinejoin="round" fill="none"/>
            <text x="2.5" y="17" fontSize="4.5" fontWeight="700"
              fill="var(--text-muted)" fontFamily="Inter, Arial">
              {isPDF ? 'PDF' : 'DOC'}
            </text>
          </svg>
        </div>

        {/* File info */}
        <div className="min-w-0">
          <p className="text-[13px] font-medium truncate max-w-[150px] leading-tight"
            style={{ color: 'var(--text-primary)' }}>
            {name}
          </p>
          <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {sizeStr} · {isPDF ? 'PDF' : 'Word'} · Phân tích EB-1A/NIW
          </p>
        </div>
      </div>

      <div className="w-7 h-7 rounded-md flex items-center justify-center text-[10px] font-bold shrink-0 mb-0.5"
        style={{ background: 'var(--border-main)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)' }}>
        B
      </div>
    </div>
  );
}
