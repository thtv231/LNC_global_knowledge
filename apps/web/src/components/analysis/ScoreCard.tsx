import { RingGauge } from './RingGauge'

export type RiskLevel = 'danger' | 'warn' | 'ok' | 'strong' | 'neutral'

export interface ScoreData {
  label: string
  score: number
  maxScore: number
  riskText: string
  riskLevel: RiskLevel
  recommended?: boolean
}

const RISK_CONFIG: Record<RiskLevel, { color: string; textColor: string; bg: string; gauge: string }> = {
  danger:  { color: '#C0392B', textColor: '#C0392B', bg: '#FDECEA', gauge: '#C0392B' },
  warn:    { color: '#BA7517', textColor: '#BA7517', bg: '#FEF3E2', gauge: '#BA7517' },
  ok:      { color: '#3B6D11', textColor: '#3B6D11', bg: '#EAF3DE', gauge: '#C9A96E' },
  strong:  { color: '#1A5C8A', textColor: '#1A5C8A', bg: '#E8F4FD', gauge: '#1A5C8A' },
  neutral: { color: '#8A9BAD', textColor: '#8A9BAD', bg: '#F7F4EF', gauge: '#8A9BAD' },
}

export function ScoreCard({ data }: { data: ScoreData }) {
  const cfg = RISK_CONFIG[data.riskLevel]

  return (
    <div
      className="rounded-lg p-4 relative overflow-hidden"
      style={{
        background: data.recommended ? '#FDFBF7' : '#FFFFFF',
        border: data.recommended ? '1.5px solid var(--gold)' : '1px solid var(--border-main)',
      }}
    >
      {data.recommended && (
        <span
          className="absolute top-0 right-0 text-[9px] font-semibold tracking-widest px-2.5 py-1 rounded-bl-lg"
          style={{ background: 'var(--gold)', color: 'var(--navy-deep)' }}
        >
          KHUYẾN NGHỊ
        </span>
      )}

      <p className="text-[11px] font-semibold tracking-widest uppercase mb-3"
        style={{ color: 'var(--text-muted)' }}>
        {data.label}
      </p>

      <div className="flex items-end gap-3 mb-2.5">
        <RingGauge value={data.score} max={data.maxScore} color={cfg.gauge} />
        <div className="flex items-baseline gap-1">
          <span className="text-[30px] font-semibold leading-none" style={{ color: 'var(--text-primary)' }}>
            {data.score}
          </span>
          <span className="text-sm mb-0.5" style={{ color: 'var(--text-faint)' }}>/{data.maxScore}</span>
        </div>
      </div>

      <p className="text-[11px] leading-snug font-medium px-2 py-1 rounded"
        style={{ color: cfg.textColor, background: cfg.bg }}>
        {data.riskText}
      </p>
    </div>
  )
}
