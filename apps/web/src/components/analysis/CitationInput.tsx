import { useState } from 'react'

interface CitationInputProps {
  onSubmit: (url: string) => void
}

export function CitationInput({ onSubmit }: CitationInputProps) {
  const [url, setUrl] = useState('')

  return (
    <div className="flex gap-3 items-start rounded-lg p-4"
      style={{ background: '#FFFFFF', border: '1px solid var(--border-main)' }}>
      <div className="w-8 h-8 rounded-md flex items-center justify-center shrink-0 mt-0.5"
        style={{ background: 'var(--bg-page)', border: '1px solid var(--border-main)' }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="var(--text-muted)" strokeWidth="1.5" aria-hidden="true">
          <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414A1 1 0 0121 9.414V19a2 2 0 01-2 2z"/>
        </svg>
      </div>
      <div className="flex-1">
        <p className="text-[12.5px] leading-snug mb-2.5" style={{ color: 'var(--text-secondary)' }}>
          AI chưa tìm thấy{' '}
          <strong className="font-medium" style={{ color: 'var(--text-primary)' }}>
            số lượt trích dẫn (Citations)
          </strong>{' '}
          trong CV. Dán link Google Scholar hoặc ResearchGate để cập nhật điểm.
        </p>
        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://scholar.google.com/citations?user=..."
            className="flex-1 px-3 py-1.5 text-[12px] rounded-[6px] outline-none transition-colors"
            style={{
              background: 'var(--bg-page)',
              border: '1px solid var(--border-soft)',
              color: 'var(--text-primary)',
            }}
            onFocus={e => (e.target.style.borderColor = 'var(--gold)')}
            onBlur={e => (e.target.style.borderColor = 'var(--border-soft)')}
          />
          <button
            onClick={() => url.trim() && onSubmit(url.trim())}
            className="px-3.5 py-1.5 rounded-[6px] text-[12px] font-semibold transition-opacity hover:opacity-90 whitespace-nowrap"
            style={{ background: 'var(--gold)', color: 'var(--navy-deep)' }}
          >
            Cập nhật
          </button>
        </div>
      </div>
    </div>
  )
}
