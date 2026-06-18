import { useState } from 'react';
import type { Message } from '../types/chat';
import { MarkdownText } from './MarkdownText';
import { CitationPanel } from './CitationPanel';
import { SuggestionChips } from './SuggestionChips';
import { IntakeCard } from './IntakeCard';
import { ConsultantCard } from './ConsultantCard';
import { CVFileBubble } from './CVFileBubble';
import { CVAnalyzingCardAuto } from './CVAnalyzingCard';
import { CVResultBubble } from './CVResultBubble';

interface Props {
  message: Message;
  messages: Message[];
  isLoading: boolean;
  sessionId: string;
  onSuggestionSelect: (q: string) => void;
}

export function MessageBubble({ message, messages, isLoading, sessionId, onSuggestionSelect }: Props) {
  const [showConsultant, setShowConsultant] = useState(true);
  const [showForm, setShowForm] = useState(message.contact_form ?? false);
  const isUser = message.role === 'user';

  if (message.cvType === 'cv-file' && message.cvFile) {
    return <CVFileBubble name={message.cvFile.name} size={message.cvFile.size} />;
  }
  if (message.cvType === 'cv-analyzing') {
    return <CVAnalyzingCardAuto />;
  }
  if (message.cvType === 'cv-result' && message.cvData) {
    return <CVResultBubble data={message.cvData} onAction={onSuggestionSelect} />;
  }

  if (isUser) {
    return (
      <div className="flex justify-end mb-4 gap-2.5 items-end msg-enter">
        <div className="max-w-[72%] px-4 py-2.5 rounded-2xl rounded-br-sm text-sm leading-relaxed"
          style={{ background: 'var(--border-soft)', color: 'var(--text-primary)' }}>
          {message.content}
        </div>
        <div className="w-7 h-7 rounded-md flex items-center justify-center text-[10px] font-bold shrink-0 mb-0.5"
          style={{ background: 'var(--border-main)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)' }}>
          B
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-4 gap-2.5 items-start msg-enter">
      {/* Bot avatar */}
      <div className="w-8 h-8 rounded-md flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-semibold tracking-wide"
        style={{ background: 'var(--navy-deep)', color: 'var(--gold)', border: '1px solid var(--navy-mid)' }}>
        L&C
      </div>

      {/* Bubble */}
      <div className="max-w-[82%] rounded-2xl rounded-tl-sm px-5 py-3.5"
        style={{ background: '#FFFFFF', border: '1px solid var(--border-main)' }}>

        {/* Web results */}
        {message.webResults && message.webResults.length > 0 && (
          <div className="mb-3 rounded-lg overflow-hidden" style={{ border: '1px solid var(--risk-ok-border)' }}>
            <div className="flex items-center gap-1.5 px-3 py-1.5" style={{ background: 'var(--risk-ok-bg)' }}>
              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: 'var(--risk-ok)' }} />
              <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: 'var(--risk-ok)' }}>
                Tìm kiếm web · mới nhất
              </span>
            </div>
            <div className="divide-y" style={{ borderColor: 'var(--border-main)' }}>
              {message.webResults.map((r, i) => {
                let host = r.url;
                try { host = new URL(r.url).hostname.replace('www.', ''); } catch { /* noop */ }
                return (
                  <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
                    className="flex gap-2 px-3 py-2 transition-colors"
                    style={{ color: 'inherit', textDecoration: 'none' }}
                    onMouseEnter={e => (e.currentTarget as HTMLAnchorElement).style.background = 'var(--bg-page)'}
                    onMouseLeave={e => (e.currentTarget as HTMLAnchorElement).style.background = 'transparent'}>
                    <span className="shrink-0 text-[9px] font-semibold mt-0.5 px-1.5 py-0.5 h-fit rounded"
                      style={{ background: 'var(--bg-page)', color: 'var(--text-muted)', border: '1px solid var(--border-soft)' }}>
                      {host}
                    </span>
                    <span className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                      {r.title}
                    </span>
                  </a>
                );
              })}
            </div>
          </div>
        )}

        {/* Content */}
        {message.content
          ? <MarkdownText content={message.content} isStreaming={message.isStreaming ?? false} />
          : message.isStreaming
            ? message.statusMessage
              ? <div className="flex items-center gap-2 py-0.5">
                  <svg className="animate-spin shrink-0 w-3.5 h-3.5" style={{ color: 'var(--gold)' }} fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                  </svg>
                  <span className="text-xs italic" style={{ color: 'var(--text-muted)' }}>{message.statusMessage}</span>
                </div>
              : <span className="flex gap-1 items-center h-5">
                  <span className="typing-dot w-1.5 h-1.5 rounded-full" style={{ background: 'var(--text-faint)' }} />
                  <span className="typing-dot w-1.5 h-1.5 rounded-full" style={{ background: 'var(--text-faint)' }} />
                  <span className="typing-dot w-1.5 h-1.5 rounded-full" style={{ background: 'var(--text-faint)' }} />
                </span>
            : null
        }

        <IntakeCard options={message.intake_options ?? []} onSelect={onSuggestionSelect} disabled={isLoading} variant="program" />

        {message.consultant_ask && showConsultant && !message.isStreaming && (
          showForm ? (
            <ConsultantCard
              profileSummary={(() => {
                const idx = messages.findIndex(m => m.id === message.id);
                const prev = messages.slice(0, idx).reverse().find(m => m.role === 'user');
                return prev?.content ?? '';
              })()}
              messages={messages}
              sessionId={sessionId}
              startAtForm={true}
              onContinueChat={() => setShowConsultant(false)}
            />
          ) : (
            <div className="mt-3 pt-3 space-y-1.5" style={{ borderTop: '1px solid var(--border-main)' }}>
              <button onClick={() => setShowForm(true)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-sm transition-all"
                style={{ border: '1px solid var(--border-soft)', background: 'var(--bg-page)', color: 'var(--text-secondary)' }}
                onMouseEnter={e => { const el = e.currentTarget as HTMLButtonElement; el.style.borderColor = 'var(--gold-border)'; el.style.background = 'var(--bg-muted)'; }}
                onMouseLeave={e => { const el = e.currentTarget as HTMLButtonElement; el.style.borderColor = 'var(--border-soft)'; el.style.background = 'var(--bg-page)'; }}>
                <span className="shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-xs font-semibold"
                  style={{ background: 'var(--navy-deep)', color: 'var(--gold)' }}>1</span>
                <span className="flex-1">Có, chuyên viên L&C liên hệ tôi trực tiếp</span>
                <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" style={{ color: 'var(--text-muted)' }}><path d="M5 12h14M12 5l7 7-7 7"/></svg>
              </button>
              <button onClick={() => setShowConsultant(false)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-sm transition-all"
                style={{ border: '1px solid var(--border-soft)', background: 'var(--bg-page)', color: 'var(--text-secondary)' }}
                onMouseEnter={e => { const el = e.currentTarget as HTMLButtonElement; el.style.borderColor = 'var(--border-soft)'; el.style.background = 'var(--bg-muted)'; }}
                onMouseLeave={e => { const el = e.currentTarget as HTMLButtonElement; el.style.borderColor = 'var(--border-soft)'; el.style.background = 'var(--bg-page)'; }}>
                <span className="shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-xs font-semibold"
                  style={{ background: 'var(--text-muted)', color: '#fff' }}>2</span>
                <span className="flex-1">Không, tiếp tục hỏi chatbot</span>
                <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" style={{ color: 'var(--text-muted)' }}><path d="M5 12h14M12 5l7 7-7 7"/></svg>
              </button>
            </div>
          )
        )}

        <CitationPanel sources={message.sources ?? []} />
        <SuggestionChips suggestions={message.suggestions ?? []} onSelect={onSuggestionSelect} disabled={isLoading} />
      </div>
    </div>
  );
}
