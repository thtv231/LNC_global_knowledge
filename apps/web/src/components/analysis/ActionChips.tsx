import type { ReactElement } from 'react'

interface ActionChipsProps {
  actions: string[]
  onAction: (action: string) => void
}

const ICONS: Record<string, ReactElement> = {
  'Xem báo cáo đầy đủ': (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414A1 1 0 0121 9.414V19a2 2 0 01-2 2z"/>
    </svg>
  ),
  'Tư duy phân tích': (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M9.663 17h4.673M12 3a4 4 0 014 4c0 2.5-2 4-4 6-2-2-4-3.5-4-6a4 4 0 014-4z"/>
    </svg>
  ),
  'Viết thư Reviewer': (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
    </svg>
  ),
}

export function ActionChips({ actions, onAction }: ActionChipsProps) {
  return (
    <div className="flex gap-2 flex-wrap">
      {actions.map(action => (
        <button key={action} onClick={() => onAction(action)}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-[6px] text-[12px] transition-colors"
          style={{
            background: '#FFFFFF',
            border: '1px solid var(--border-soft)',
            color: 'var(--text-secondary)',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--gold-border)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border-soft)'; }}
        >
          {ICONS[action] ?? null}
          {action}
        </button>
      ))}
    </div>
  )
}
