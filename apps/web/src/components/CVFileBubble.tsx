interface Props { name: string; size: number; }

export function CVFileBubble({ name, size }: Props) {
  const kb = size / 1024;
  const sizeStr = kb > 1024 ? (kb / 1024).toFixed(1) + ' MB' : Math.round(kb) + ' KB';
  const isPDF = name.toLowerCase().endsWith('.pdf');

  return (
    <div className="flex justify-end mb-4 gap-2.5 items-end msg-enter">
      <div className="flex items-center gap-3 rounded-2xl rounded-br-sm px-3.5 py-3 max-w-[260px]"
        style={{ background: 'var(--navy-deep)', border: '1px solid var(--navy-mid)' }}>

        {/* File type badge */}
        <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: 'rgba(201,169,110,0.15)', border: '1px solid var(--gold-border)' }}>
          <svg width="18" height="20" viewBox="0 0 20 22" fill="none">
            <rect x="1" y="1" width="14" height="20" rx="2"
              stroke="var(--gold)" strokeWidth="1.5"/>
            <polyline points="5 1 5 6 1 6"
              stroke="var(--gold)" strokeWidth="1.5" strokeLinejoin="round" fill="none"/>
            <text x="2.5" y="17" fontSize="4.5" fontWeight="700"
              fill="var(--gold)" fontFamily="Inter, Arial">
              {isPDF ? 'PDF' : 'DOC'}
            </text>
          </svg>
        </div>

        {/* File info */}
        <div className="min-w-0">
          <p className="text-[13px] font-medium truncate max-w-[150px] leading-tight"
            style={{ color: '#F7F4EF' }}>
            {name}
          </p>
          <p className="text-[11px] mt-0.5" style={{ color: 'rgba(201,169,110,0.7)' }}>
            {sizeStr} · {isPDF ? 'PDF' : 'Word'} · Phân tích EB-1A/NIW
          </p>
        </div>
      </div>

      <div className="w-7 h-7 rounded-md flex items-center justify-center text-[10px] font-bold shrink-0 mb-0.5"
        style={{ background: 'var(--navy-mid)', color: 'var(--gold)', border: '1px solid rgba(201,169,110,0.3)' }}>
        B
      </div>
    </div>
  );
}
