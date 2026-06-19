# UI_REDESIGN.md — LNC Chatbot Frontend Redesign

> Hướng dẫn cho Claude Code thực hiện redesign giao diện chatbot L&C Global.  
> Stack: **React** (Vite) + **TailwindCSS** + **NestJS** gateway + **FastAPI** LangGraph service.

---

## Mục tiêu

Nâng cấp giao diện chatbot từ tone SaaS xanh lá → tone **premium immigration consulting**:
- Màu chủ đạo: Navy `#0D1B2A` + Gold `#C9A96E` + Warm off-white `#F7F4EF`
- Score cards với ring gauge SVG thay progress bar ngang
- Hierarchy rõ ràng, typography nhất quán
- Dark mode optional (ưu tiên light trước)

---

## Cấu trúc file cần tạo / chỉnh sửa

```
frontend/
├── src/
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatWindow.tsx          ← layout chính
│   │   │   ├── MessageBubble.tsx       ← bubble user / AI
│   │   │   ├── ChatInput.tsx           ← input bar + send
│   │   │   └── SuggestionChips.tsx     ← chip gợi ý
│   │   ├── analysis/
│   │   │   ├── AnalysisCard.tsx        ← wrapper kết quả phân tích
│   │   │   ├── ScoreCard.tsx           ← card điểm EB-1A / EB-2 NIW
│   │   │   ├── RingGauge.tsx           ← SVG ring gauge
│   │   │   ├── CitationInput.tsx       ← input Google Scholar link
│   │   │   └── ActionChips.tsx         ← nút báo cáo / tư duy phân tích
│   │   └── layout/
│   │       ├── TopBar.tsx              ← header navigation
│   │       └── CtaBanner.tsx           ← nút đăng ký tư vấn
│   ├── hooks/
│   │   ├── useChat.ts                  ← logic chat + SSE stream
│   │   └── useAnalysis.ts             ← parse kết quả phân tích từ AI
│   ├── styles/
│   │   └── tokens.css                 ← CSS custom properties (màu, font)
│   └── App.tsx
└── tailwind.config.ts
```

---

## 1. Design Tokens — `src/styles/tokens.css`

Tạo file này và import vào `main.tsx`:

```css
:root {
  /* Brand */
  --navy-deep:    #0D1B2A;
  --navy-mid:     #1A3A5C;
  --gold:         #C9A96E;
  --gold-light:   rgba(201, 169, 110, 0.15);
  --gold-border:  rgba(201, 169, 110, 0.4);

  /* Surfaces */
  --bg-page:      #F7F4EF;
  --bg-white:     #FFFFFF;
  --bg-muted:     #FDFBF7;

  /* Borders */
  --border-main:  #E8E0D4;
  --border-soft:  #D4C9B8;

  /* Text */
  --text-primary:   #0D1B2A;
  --text-secondary: #4A4235;
  --text-muted:     #8A9BAD;
  --text-faint:     #B0A090;

  /* Semantic */
  --risk-warn:    #BA7517;
  --risk-ok:      #3B6D11;
  --risk-ok-bg:   #EAF3DE;
  --risk-ok-border: #C0DD97;

  /* Spacing */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
}
```

---

## 2. Tailwind Config — `tailwind.config.ts`

Extend theme để dùng được token trong class:

```ts
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy:  { deep: '#0D1B2A', mid: '#1A3A5C' },
        gold:  { DEFAULT: '#C9A96E', light: 'rgba(201,169,110,0.15)' },
        page:  '#F7F4EF',
        muted: '#FDFBF7',
        border: { main: '#E8E0D4', soft: '#D4C9B8' },
        text:  {
          primary:   '#0D1B2A',
          secondary: '#4A4235',
          muted:     '#8A9BAD',
          faint:     '#B0A090',
        },
        risk: {
          warn:      '#BA7517',
          ok:        '#3B6D11',
          'ok-bg':   '#EAF3DE',
          'ok-border': '#C0DD97',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        sm: '6px',
        md: '8px',
        lg: '12px',
      },
    },
  },
  plugins: [],
} satisfies Config
```

---

## 3. TopBar — `src/components/layout/TopBar.tsx`

```tsx
interface TopBarProps {
  onNewChat: () => void
}

export function TopBar({ onNewChat }: TopBarProps) {
  return (
    <header className="bg-navy-deep px-5 py-3 flex items-center justify-between">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-[34px] h-[34px] bg-gold rounded-md flex items-center justify-center
                        text-navy-deep text-[13px] font-semibold tracking-wide">
          L&C
        </div>
        <div>
          <p className="text-page text-sm font-medium tracking-tight">
            L&C Global — Tư vấn Định cư
          </p>
          <p className="text-text-muted text-[11px] mt-[1px]">
            Canada · Mỹ · New Zealand
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={onNewChat}
          className="bg-gold-light text-gold border border-gold-border
                     px-3 py-1.5 rounded-full text-[11px] font-medium tracking-wide
                     hover:bg-gold/20 transition-colors"
        >
          + Cuộc trò chuyện mới
        </button>
        <span className="bg-gold-light text-gold border border-gold-border
                         px-3 py-1.5 rounded-full text-[11px] font-medium tracking-wide">
          AI · deepseek
        </span>
      </div>
    </header>
  )
}
```

---

## 4. RingGauge — `src/components/analysis/RingGauge.tsx`

Component SVG dùng lại cho mọi score card:

```tsx
interface RingGaugeProps {
  value: number       // điểm thực tế
  max: number         // điểm tối đa
  color?: string      // hex color của vòng tròn
  size?: number       // px, default 52
}

export function RingGauge({
  value,
  max,
  color = '#C9A96E',
  size = 52,
}: RingGaugeProps) {
  const r = (size / 2) - 4          // radius trừ stroke width
  const circumference = 2 * Math.PI * r
  const filled = (value / max) * circumference
  const empty = circumference - filled
  // Offset để bắt đầu từ top (12 giờ): -circumference * 0.25
  const offset = -(circumference * 0.25)

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      {/* Track */}
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke="#E8E0D4" strokeWidth="4"
      />
      {/* Fill */}
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
```

---

## 5. ScoreCard — `src/components/analysis/ScoreCard.tsx`

```tsx
import { RingGauge } from './RingGauge'

export interface ScoreData {
  label: string           // 'EB-1A' | 'EB-2 NIW'
  score: number           // 4
  maxScore: number        // 10
  riskText: string        // 'Rủi ro cao · RFE ~50–60%'
  riskLevel: 'warn' | 'ok' | 'neutral'
  recommended?: boolean
}

const RISK_STYLES: Record<ScoreData['riskLevel'], string> = {
  warn:    'text-risk-warn',
  ok:      'text-risk-ok',
  neutral: 'text-text-muted',
}

const GAUGE_COLOR: Record<ScoreData['riskLevel'], string> = {
  warn:    '#BA7517',
  ok:      '#C9A96E',
  neutral: '#8A9BAD',
}

export function ScoreCard({ data }: { data: ScoreData }) {
  return (
    <div
      className={`
        bg-white rounded-lg p-4 relative overflow-hidden
        ${data.recommended
          ? 'border-[1.5px] border-gold bg-muted'
          : 'border border-border-main'}
      `}
    >
      {/* Recommended badge */}
      {data.recommended && (
        <span className="absolute top-0 right-0 bg-gold text-navy-deep
                         text-[9px] font-semibold tracking-widest px-2.5 py-1
                         rounded-bl-lg">
          KHUYẾN NGHỊ
        </span>
      )}

      {/* Label */}
      <p className="text-[11px] font-semibold text-text-muted tracking-widest uppercase mb-3">
        {data.label}
      </p>

      {/* Gauge + Score */}
      <div className="flex items-end gap-3 mb-3">
        <RingGauge
          value={data.score}
          max={data.maxScore}
          color={GAUGE_COLOR[data.riskLevel]}
        />
        <div className="flex items-baseline gap-1">
          <span className="text-[32px] font-semibold text-text-primary leading-none">
            {data.score}
          </span>
          <span className="text-sm text-text-faint mb-1">/{data.maxScore}</span>
        </div>
      </div>

      {/* Risk text */}
      <p className={`text-[11px] leading-snug ${RISK_STYLES[data.riskLevel]}`}>
        {data.riskText}
      </p>
    </div>
  )
}
```

---

## 6. CitationInput — `src/components/analysis/CitationInput.tsx`

```tsx
import { useState } from 'react'

interface CitationInputProps {
  onSubmit: (url: string) => void
}

export function CitationInput({ onSubmit }: CitationInputProps) {
  const [url, setUrl] = useState('')

  return (
    <div className="bg-white border border-border-main rounded-lg p-4 flex gap-3 items-start">
      {/* Icon */}
      <div className="w-8 h-8 bg-page border border-border-main rounded-md
                      flex items-center justify-center flex-shrink-0 mt-0.5">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
             stroke="#8A9BAD" strokeWidth="1.5" aria-hidden="true">
          <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586
                   a1 1 0 01.707.293l5.414 5.414A1 1 0 0121 9.414V19a2 2 0 01-2 2z"/>
        </svg>
      </div>

      <div className="flex-1">
        <p className="text-[12.5px] text-text-secondary leading-snug mb-2.5">
          AI chưa tìm thấy{' '}
          <strong className="text-text-primary font-medium">
            số lượt trích dẫn (Citations)
          </strong>{' '}
          trong CV. Dán link Google Scholar hoặc ResearchGate để cập nhật điểm.
        </p>
        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://scholar.google.com/citations?user=..."
            className="flex-1 bg-page border border-border-soft rounded-[6px]
                       px-3 py-1.5 text-[12px] text-text-primary placeholder:text-text-faint
                       focus:outline-none focus:border-gold transition-colors"
          />
          <button
            onClick={() => url.trim() && onSubmit(url.trim())}
            className="bg-gold text-navy-deep px-3.5 py-1.5 rounded-[6px]
                       text-[12px] font-semibold hover:bg-gold/90 transition-colors
                       whitespace-nowrap"
          >
            Cập nhật
          </button>
        </div>
      </div>
    </div>
  )
}
```

---

## 7. AnalysisCard — `src/components/analysis/AnalysisCard.tsx`

Container render toàn bộ kết quả phân tích khi AI trả về structured data:

```tsx
import { ScoreCard, ScoreData } from './ScoreCard'
import { CitationInput } from './CitationInput'
import { ActionChips } from './ActionChips'

interface AnalysisResult {
  duration: number          // giây
  scores: ScoreData[]
  hasCitations: boolean
  suggestions: string[]     // chip gợi ý hành động
}

interface AnalysisCardProps {
  result: AnalysisResult
  onCitationSubmit: (url: string) => void
  onActionClick: (action: string) => void
  onSuggestionClick: (text: string) => void
}

export function AnalysisCard({
  result,
  onCitationSubmit,
  onActionClick,
  onSuggestionClick,
}: AnalysisCardProps) {
  return (
    <div className="flex flex-col gap-3">
      {/* Status */}
      <div className="flex items-center gap-2 bg-risk-ok-bg border border-risk-ok-border
                      rounded-md px-3.5 py-2">
        <span className="w-[7px] h-[7px] bg-risk-ok rounded-full flex-shrink-0" />
        <span className="text-[12px] font-medium text-risk-ok">
          Phân tích hồ sơ hoàn tất · {result.duration.toFixed(2)}s
        </span>
      </div>

      {/* Score cards */}
      <div className="grid grid-cols-2 gap-3">
        {result.scores.map((score) => (
          <ScoreCard key={score.label} data={score} />
        ))}
      </div>

      {/* Citation input nếu thiếu data */}
      {!result.hasCitations && (
        <CitationInput onSubmit={onCitationSubmit} />
      )}

      {/* Action chips */}
      <ActionChips
        actions={['Xem báo cáo đầy đủ', 'Tư duy phân tích']}
        onAction={onActionClick}
      />

      {/* Suggestion chips */}
      <div className="flex flex-col gap-2">
        {result.suggestions.map((s) => (
          <button
            key={s}
            onClick={() => onSuggestionClick(s)}
            className="bg-white border border-border-soft rounded-md
                       px-4 py-2 text-[12.5px] text-navy-mid
                       flex items-center gap-2 hover:border-gold/50 transition-colors text-left"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                 stroke="#C9A96E" strokeWidth="1.5" aria-hidden="true">
              <path d="M15.232 5.232l3.536 3.536M9 11l4 4L21 7M3 17v4h4l11-11-4-4L3 17z"/>
            </svg>
            {s} ↗
          </button>
        ))}
      </div>
    </div>
  )
}
```

---

## 8. ActionChips — `src/components/analysis/ActionChips.tsx`

```tsx
interface ActionChipsProps {
  actions: string[]
  onAction: (action: string) => void
}

const ICONS: Record<string, JSX.Element> = {
  'Xem báo cáo đầy đủ': (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586
               a1 1 0 01.707.293l5.414 5.414A1 1 0 0121 9.414V19a2 2 0 01-2 2z"/>
    </svg>
  ),
  'Tư duy phân tích': (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M9.663 17h4.673M12 3a4 4 0 014 4c0 2.5-2 4-4 6-2-2-4-3.5-4-6a4 4 0 014-4z"/>
    </svg>
  ),
}

export function ActionChips({ actions, onAction }: ActionChipsProps) {
  return (
    <div className="flex gap-2 flex-wrap">
      {actions.map((action) => (
        <button
          key={action}
          onClick={() => onAction(action)}
          className="bg-white border border-border-soft rounded-md
                     px-3.5 py-1.5 text-[12px] text-text-secondary
                     flex items-center gap-1.5 hover:border-gold/50 transition-colors"
        >
          {ICONS[action]}
          {action}
        </button>
      ))}
    </div>
  )
}
```

---

## 9. SuggestionChips — `src/components/chat/SuggestionChips.tsx`

Hiển thị chips gợi ý câu hỏi nhanh khi chat trống:

```tsx
const DEFAULT_SUGGESTIONS = [
  'Tôi có đủ điều kiện EB-2 NIW không?',
  'So sánh Express Entry và EB-3',
  'Thời gian xử lý hồ sơ Canada 2025',
  'Yêu cầu tối thiểu để apply New Zealand',
]

interface SuggestionChipsProps {
  onSelect: (text: string) => void
  suggestions?: string[]
}

export function SuggestionChips({
  onSelect,
  suggestions = DEFAULT_SUGGESTIONS,
}: SuggestionChipsProps) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 px-4">
      <p className="text-text-muted text-[13px] mb-1">Bắt đầu với một câu hỏi</p>
      <div className="flex flex-wrap justify-center gap-2">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => onSelect(s)}
            className="bg-white border border-border-main rounded-md
                       px-4 py-2 text-[12.5px] text-text-secondary
                       hover:border-gold/60 hover:text-navy-deep transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}
```

---

## 10. ChatInput — `src/components/chat/ChatInput.tsx`

```tsx
import { useState, KeyboardEvent } from 'react'

interface ChatInputProps {
  onSend: (text: string) => void
  disabled?: boolean
  placeholder?: string
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = 'Hỏi về định cư Canada, Mỹ, New Zealand...',
}: ChatInputProps) {
  const [value, setValue] = useState('')

  const handleSend = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex gap-2 items-center">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        className="flex-1 bg-page border border-border-soft rounded-md
                   px-4 py-2.5 text-[13px] text-text-primary
                   placeholder:text-text-faint
                   focus:outline-none focus:border-gold transition-colors
                   disabled:opacity-50"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        aria-label="Gửi tin nhắn"
        className="w-[38px] h-[38px] bg-navy-deep rounded-md flex items-center justify-center
                   hover:bg-navy-mid transition-colors flex-shrink-0
                   disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
             stroke="#C9A96E" strokeWidth="2" aria-hidden="true">
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
        </svg>
      </button>
    </div>
  )
}
```

---

## 11. MessageBubble — `src/components/chat/MessageBubble.tsx`

```tsx
import { AnalysisCard } from '../analysis/AnalysisCard'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  analysisResult?: any    // structured data nếu AI trả về phân tích
  isStreaming?: boolean
}

interface MessageBubbleProps {
  message: Message
  onCitationSubmit?: (url: string) => void
  onSuggestionClick?: (text: string) => void
  onActionClick?: (action: string) => void
}

export function MessageBubble({
  message,
  onCitationSubmit,
  onSuggestionClick,
  onActionClick,
}: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      {!isUser && (
        <div className="w-8 h-8 bg-navy-deep rounded-full flex items-center justify-center
                        flex-shrink-0 mt-1">
          <span className="text-gold text-[11px] font-semibold">AI</span>
        </div>
      )}

      <div className={`flex flex-col gap-2 max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Bubble text */}
        {message.content && (
          <div
            className={`
              px-4 py-2.5 rounded-lg text-[13px] leading-relaxed
              ${isUser
                ? 'bg-navy-deep text-page rounded-tr-sm'
                : 'bg-white border border-border-main text-text-secondary rounded-tl-sm'}
              ${message.isStreaming ? 'after:content-["▋"] after:animate-pulse after:text-gold' : ''}
            `}
          >
            {message.content}
          </div>
        )}

        {/* Analysis card nếu có */}
        {message.analysisResult && (
          <AnalysisCard
            result={message.analysisResult}
            onCitationSubmit={onCitationSubmit ?? (() => {})}
            onActionClick={onActionClick ?? (() => {})}
            onSuggestionClick={onSuggestionClick ?? (() => {})}
          />
        )}
      </div>
    </div>
  )
}
```

---

## 12. CtaBanner — `src/components/layout/CtaBanner.tsx`

```tsx
interface CtaBannerProps {
  onClick: () => void
}

export function CtaBanner({ onClick }: CtaBannerProps) {
  return (
    <button
      onClick={onClick}
      className="w-full bg-navy-deep text-gold rounded-md py-3 px-5
                 text-[13px] font-semibold tracking-wide
                 flex items-center justify-center gap-2
                 hover:bg-navy-mid transition-colors"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
        <path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7
                 a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
      </svg>
      Đăng ký tư vấn chuyên sâu với L&C Global
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
        <path d="M9 5l7 7-7 7"/>
      </svg>
    </button>
  )
}
```

---

## 13. ChatWindow — `src/components/chat/ChatWindow.tsx`

Layout tổng hợp tất cả component:

```tsx
import { useRef, useEffect } from 'react'
import { TopBar } from '../layout/TopBar'
import { MessageBubble, Message } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { SuggestionChips } from './SuggestionChips'
import { CtaBanner } from '../layout/CtaBanner'
import { useChat } from '../../hooks/useChat'

export function ChatWindow() {
  const { messages, isStreaming, sendMessage, clearMessages } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const isEmpty = messages.length === 0

  return (
    <div className="flex flex-col h-screen bg-page">
      {/* Header */}
      <TopBar onNewChat={clearMessages} />

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-5 py-5 flex flex-col gap-4">
        {isEmpty ? (
          <SuggestionChips onSelect={sendMessage} />
        ) : (
          messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onCitationSubmit={(url) => sendMessage(`Citation URL: ${url}`)}
              onSuggestionClick={sendMessage}
              onActionClick={(action) => sendMessage(action)}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Bottom bar */}
      <div className="bg-white border-t border-border-main px-4 py-3 flex flex-col gap-2.5">
        <CtaBanner onClick={() => window.open('https://lncglobal.vn/tu-van', '_blank')} />
        <ChatInput onSend={sendMessage} disabled={isStreaming} />
        <p className="text-[10.5px] text-text-faint text-center tracking-wide">
          AI có thể mắc lỗi · Vui lòng xác minh với nguồn chính thức
        </p>
      </div>
    </div>
  )
}
```

---

## 14. useChat Hook — `src/hooks/useChat.ts`

Hook quản lý state + SSE stream từ NestJS gateway:

```ts
import { useState, useCallback, useRef } from 'react'
import { Message } from '../components/chat/MessageBubble'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:3001'

function generateId() {
  return Math.random().toString(36).slice(2, 9)
}

// Parse JSON nếu AI trả về structured analysis
function tryParseAnalysis(text: string) {
  try {
    const match = text.match(/```json\n([\s\S]+?)\n```/)
    if (match) return JSON.parse(match[1])
  } catch {}
  return null
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return

    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content: text,
    }

    const aiMsgId = generateId()
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    }

    setMessages((prev) => [...prev, userMsg, aiMsg])
    setIsStreaming(true)

    abortRef.current = new AbortController()

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
        signal: abortRef.current.signal,
      })

      if (!res.body) throw new Error('No response body')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let accumulated = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })

        // SSE format: "data: <token>\n\n"
        const lines = chunk.split('\n')
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const token = line.slice(6)
            if (token === '[DONE]') break
            accumulated += token

            setMessages((prev) =>
              prev.map((m) =>
                m.id === aiMsgId
                  ? { ...m, content: accumulated }
                  : m
              )
            )
          }
        }
      }

      // Sau khi stream xong, parse analysis nếu có
      const analysisResult = tryParseAnalysis(accumulated)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsgId
            ? { ...m, isStreaming: false, analysisResult }
            : m
        )
      )
    } catch (err: any) {
      if (err.name === 'AbortError') return
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsgId
            ? { ...m, content: 'Có lỗi xảy ra. Vui lòng thử lại.', isStreaming: false }
            : m
        )
      )
    } finally {
      setIsStreaming(false)
    }
  }, [isStreaming])

  const clearMessages = useCallback(() => {
    abortRef.current?.abort()
    setMessages([])
    setIsStreaming(false)
  }, [])

  return { messages, isStreaming, sendMessage, clearMessages }
}
```

---

## 15. useAnalysis Hook — `src/hooks/useAnalysis.ts`

Parse structured output từ AI thành `AnalysisResult`:

```ts
import type { ScoreData } from '../components/analysis/ScoreCard'

export interface AnalysisResult {
  duration: number
  scores: ScoreData[]
  hasCitations: boolean
  suggestions: string[]
}

// Gọi sau khi nhận full response từ AI (khi stream kết thúc)
export function parseAnalysisFromResponse(raw: string): AnalysisResult | null {
  try {
    const jsonMatch = raw.match(/```json\n([\s\S]+?)\n```/)
    if (!jsonMatch) return null

    const data = JSON.parse(jsonMatch[1])

    return {
      duration: data.duration ?? 0,
      hasCitations: data.has_citations ?? false,
      suggestions: data.suggestions ?? [],
      scores: (data.scores ?? []).map((s: any): ScoreData => ({
        label: s.label,
        score: s.score,
        maxScore: s.max_score,
        riskText: s.risk_text,
        riskLevel: s.risk_level ?? 'neutral',
        recommended: s.recommended ?? false,
      })),
    }
  } catch {
    return null
  }
}
```

---

## 16. App.tsx

```tsx
import './styles/tokens.css'
import { ChatWindow } from './components/chat/ChatWindow'

export default function App() {
  return <ChatWindow />
}
```

---

## 17. Cấu trúc JSON AI cần trả về (LangGraph generator node)

Khi kết quả là phân tích hồ sơ, AI **phải** trả về block JSON sau trong response, bọc bằng ``` ```json ```:

```json
{
  "duration": 44.21,
  "has_citations": false,
  "scores": [
    {
      "label": "EB-1A",
      "score": 4,
      "max_score": 10,
      "risk_text": "Rủi ro cao · RFE ~50–60%",
      "risk_level": "warn",
      "recommended": false
    },
    {
      "label": "EB-2 NIW",
      "score": 5,
      "max_score": 9,
      "risk_text": "Đủ điều kiện cơ bản · Gap 6–12 tháng",
      "risk_level": "ok",
      "recommended": true
    }
  ],
  "suggestions": [
    "Viết thư mẫu xin làm Reviewer tạp chí quốc tế",
    "Xem checklist tài liệu EB-2 NIW cần chuẩn bị"
  ]
}
```

Sau JSON block, AI tiếp tục viết text thường cho phần giải thích narrative.

---

## 18. Thứ tự thực hiện (Build Order)

```
1.  Cài Inter font: thêm vào index.html
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">

2.  Tạo src/styles/tokens.css và import vào main.tsx

3.  Cập nhật tailwind.config.ts với design tokens

4.  Tạo src/components/analysis/RingGauge.tsx

5.  Tạo src/components/analysis/ScoreCard.tsx

6.  Tạo src/components/analysis/CitationInput.tsx

7.  Tạo src/components/analysis/ActionChips.tsx

8.  Tạo src/components/analysis/AnalysisCard.tsx

9.  Tạo src/components/layout/TopBar.tsx

10. Tạo src/components/layout/CtaBanner.tsx

11. Tạo src/components/chat/SuggestionChips.tsx

12. Tạo src/components/chat/ChatInput.tsx

13. Tạo src/components/chat/MessageBubble.tsx

14. Tạo src/hooks/useAnalysis.ts

15. Tạo src/hooks/useChat.ts

16. Tạo src/components/chat/ChatWindow.tsx

17. Cập nhật src/App.tsx

18. Kiểm tra: npm run dev → mở http://localhost:5173
    - Gửi tin nhắn thử
    - Verify ring gauge render đúng
    - Verify gold border trên recommended card
```

---

## 19. Biến môi trường cần có

```env
# frontend/.env.local
VITE_API_URL=http://localhost:3001
```

---

## 20. Gotchas

| Vấn đề | Giải pháp |
|--------|-----------|
| Ring gauge bắt đầu từ 3 giờ thay vì 12 giờ | `strokeDashoffset = -(circumference * 0.25)` |
| Tailwind không nhận custom color | Chạy `npx tailwindcss --watch` lại, clear cache |
| SSE stream bị buffer | NestJS phải có `res.flushHeaders()` và header `X-Accel-Buffering: no` |
| JSON parse fail khi stream chưa xong | Chỉ parse `analysisResult` sau khi `isStreaming = false` |
| Font Inter không load | Kiểm tra CSP header, thêm `fonts.googleapis.com` vào allowlist |
| `recommended` badge bị overflow | `overflow-hidden` trên `.lnc-score-card` — đã xử lý trong CSS |
