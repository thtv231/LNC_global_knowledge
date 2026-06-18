interface RingGaugeProps {
  value: number
  max: number
  color?: string
  size?: number
}

export function RingGauge({ value, max, color = '#C9A96E', size = 52 }: RingGaugeProps) {
  const r = (size / 2) - 4
  const circumference = 2 * Math.PI * r
  const filled = Math.min(value / max, 1) * circumference
  const empty = circumference - filled
  const offset = -(circumference * 0.25)

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E8E0D4" strokeWidth="4" />
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none"
        stroke={color}
        strokeWidth="4"
        strokeDasharray={`${filled} ${empty}`}
        strokeDashoffset={offset}
        strokeLinecap="round"
      />
    </svg>
  )
}
