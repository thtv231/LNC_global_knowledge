interface TopBarProps {
  onNewChat: () => void
  hasMessages: boolean
}

export function TopBar({ onNewChat, hasMessages }: TopBarProps) {
  return (
    <header className="px-5 py-3 flex items-center justify-between shrink-0"
      style={{ background: 'var(--navy-deep)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
      <div className="flex items-center gap-3">
        <div className="w-[34px] h-[34px] rounded-md flex items-center justify-center text-[12px] font-semibold tracking-wide shrink-0"
          style={{ background: 'var(--gold)', color: 'var(--navy-deep)' }}>
          L&C
        </div>
        <div>
          <p className="text-sm font-medium tracking-tight" style={{ color: '#F7F4EF' }}>
            L&C Global — Tư vấn Định cư
          </p>
          <p className="text-[11px] mt-[1px]" style={{ color: 'var(--text-muted)' }}>
            Canada · Mỹ · New Zealand
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {hasMessages && (
          <button onClick={onNewChat}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium tracking-wide transition-colors"
            style={{
              background: 'var(--gold-light)',
              color: 'var(--gold)',
              border: '1px solid var(--gold-border)',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(201,169,110,0.22)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--gold-light)'; }}
          >
            <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M12 5v14M5 12l7-7 7 7"/>
            </svg>
            Cuộc trò chuyện mới
          </button>
        )}
      </div>
    </header>
  )
}
