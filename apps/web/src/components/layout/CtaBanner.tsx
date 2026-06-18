interface CtaBannerProps {
  onClick: () => void
}

export function CtaBanner({ onClick }: CtaBannerProps) {
  return (
    <button onClick={onClick}
      className="w-full py-3 px-5 rounded-md text-[13px] font-semibold tracking-wide flex items-center justify-center gap-2 transition-colors"
      style={{ background: 'var(--navy-deep)', color: 'var(--gold)' }}
      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--navy-mid)'; }}
      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--navy-deep)'; }}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
      </svg>
      Đăng ký tư vấn chuyên sâu với L&C Global
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M9 5l7 7-7 7"/>
      </svg>
    </button>
  )
}
