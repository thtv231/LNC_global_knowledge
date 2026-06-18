import { useState, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { TopBar } from './layout/TopBar';
import { CtaBanner } from './layout/CtaBanner';
import { MessageBubble } from './MessageBubble';
import { MarkdownText } from './MarkdownText';
import { IntakeWizard } from './IntakeWizard';
import { CVUploadButton } from './CVUploadButton';
import { useChat } from '../hooks/useChat';
import { useSession } from '../hooks/useSession';
import type { CVAnalysisData } from '../types/chat';

const CV_API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3000';
const TUNNEL_HEADERS: Record<string, string> = CV_API_URL.includes('loca.lt')
  ? { 'bypass-tunnel-reminder': 'true' }
  : {};

const SUGGESTIONS = [
  'Điều kiện Express Entry Canada?',
  'So sánh EB2-NIW và EB1-A Mỹ',
  'Chương trình Skilled Migrant New Zealand',
  'Chi phí định cư Canada mất bao nhiêu?',
];

const WELCOME = `Xin chào! Tôi là **trợ lý AI của L&C Global**

Với hơn **12 năm kinh nghiệm** và **1.000+ hồ sơ thành công**, L&C Global đồng hành cùng Anh/Chị trên hành trình định cư toàn cầu.

Tôi có thể tư vấn về:
- **Canada** — Express Entry, PNP, LMIA, bảo lãnh gia đình
- **Mỹ** — EB-1A, EB-2 NIW, L1 Visa, Green Card
- **New Zealand** — Skilled Migrant, AEWV`;

export function ChatWindow() {
  const sessionId = useSession();
  const { messages, isLoading, serverError, setServerError, sendMessage, clearHistory, addMessage, removeMessage } = useChat(sessionId);
  const [input, setInput] = useState('');
  const [showWizard, setShowWizard] = useState(false);
  const [cvLoading, setCvLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const isBusy = isLoading || cvLoading;

  const handleCVFile = async (file: File) => {
    const fileId = uuidv4();
    const analyzingId = uuidv4();
    addMessage({ id: fileId, role: 'user', content: '', cvType: 'cv-file', cvFile: { name: file.name, size: file.size } });
    addMessage({ id: analyzingId, role: 'assistant', content: '', cvType: 'cv-analyzing' });
    setCvLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`${CV_API_URL}/cv/analyze`, { method: 'POST', body: formData, headers: TUNNEL_HEADERS });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json() as CVAnalysisData;
      removeMessage(analyzingId);
      addMessage({ id: uuidv4(), role: 'assistant', content: '', cvType: 'cv-result', cvData: data });
    } catch {
      removeMessage(analyzingId);
      addMessage({ id: uuidv4(), role: 'assistant', content: 'Có lỗi khi phân tích CV. Vui lòng thử lại.' });
    } finally {
      setCvLoading(false);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q || isBusy) return;
    setInput('');
    inputRef.current?.focus();
    await sendMessage(q);
  };

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg-page)' }}>

      {/* Server error modal */}
      {serverError && (
        <div className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(13,27,42,0.65)', backdropFilter: 'blur(4px)' }}>
          <div className="rounded-xl shadow-2xl px-8 py-7 max-w-sm mx-4 text-center"
            style={{ background: '#FFFFFF', border: '1px solid var(--border-main)' }}>
            <div className="w-11 h-11 rounded-lg flex items-center justify-center mx-auto mb-4"
              style={{ background: 'var(--navy-deep)', color: 'var(--gold)' }}>
              <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
              </svg>
            </div>
            <h2 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Server đang bảo trì</h2>
            <p className="text-[13px] mb-5" style={{ color: 'var(--text-muted)' }}>Vui lòng chờ trong chốc lát và thử lại.</p>
            <button onClick={() => setServerError(false)}
              className="px-6 py-2 rounded-md text-sm font-semibold text-white transition-opacity hover:opacity-90"
              style={{ background: 'var(--navy-deep)' }}>
              Đã hiểu
            </button>
          </div>
        </div>
      )}

      <TopBar onNewChat={clearHistory} hasMessages={messages.length > 0} />

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          /* Empty / welcome state */
          <div className="h-full flex flex-col items-center justify-center px-5 py-8">
            {/* Brand mark */}
            <div className="flex flex-col items-center mb-8">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center font-semibold text-base tracking-wide shadow-lg mb-3"
                style={{ background: 'var(--navy-deep)', color: 'var(--gold)' }}>
                L&C
              </div>
              <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                L&C Global AI Assistant
              </h2>
              <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
                Tư vấn định cư Canada · Mỹ · New Zealand
              </p>
            </div>

            {/* Welcome card */}
            <div className="w-full max-w-xl rounded-xl px-6 py-5 mb-5 fade-in"
              style={{ background: '#FFFFFF', border: '1px solid var(--border-main)' }}>
              <MarkdownText content={WELCOME} isStreaming={false} />
            </div>

            {/* Suggestion grid */}
            <div className="w-full max-w-xl grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4">
              {SUGGESTIONS.map((s, i) => (
                <button key={i} onClick={() => sendMessage(s)}
                  className="text-left text-sm px-4 py-2.5 rounded-md transition-all duration-150"
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid var(--border-main)',
                    color: 'var(--text-secondary)',
                  }}
                  onMouseEnter={e => {
                    const el = e.currentTarget as HTMLButtonElement;
                    el.style.borderColor = 'var(--gold-border)';
                    el.style.background = 'var(--bg-muted)';
                    el.style.transform = 'translateY(-1px)';
                    el.style.boxShadow = '0 3px 10px rgba(201,169,110,0.15)';
                  }}
                  onMouseLeave={e => {
                    const el = e.currentTarget as HTMLButtonElement;
                    el.style.borderColor = 'var(--border-main)';
                    el.style.background = '#FFFFFF';
                    el.style.transform = 'none';
                    el.style.boxShadow = 'none';
                  }}>
                  <span className="font-semibold mr-2 text-xs" style={{ color: 'var(--gold)' }}>→</span>{s}
                </button>
              ))}
            </div>

            <p className="text-xs" style={{ color: 'var(--text-faint)' }}>
              Hoặc <span className="font-medium" style={{ color: 'var(--gold)' }}>upload CV</span> để phân tích EB-1A / EB-2 NIW
            </p>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto px-5 py-5 flex flex-col gap-4">
            {messages.map(msg => (
              <MessageBubble
                key={msg.id}
                message={msg}
                messages={messages}
                isLoading={isLoading}
                sessionId={sessionId}
                onSuggestionSelect={sendMessage}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div style={{ background: '#FFFFFF', borderTop: '1px solid var(--border-main)' }}>
        <div className="max-w-3xl mx-auto px-4 pt-3 pb-4">
          {showWizard ? (
            <div className="mb-3">
              <IntakeWizard onClose={() => setShowWizard(false)}
                onComplete={summary => { setShowWizard(false); sendMessage(summary); }} />
            </div>
          ) : (
            <div className="mb-3">
              <CtaBanner onClick={() => setShowWizard(true)} />
            </div>
          )}

          <div className="flex gap-2 items-center">
            <CVUploadButton onFileSelect={handleCVFile} disabled={isBusy} />
            <input ref={inputRef}
              className="flex-1 px-4 py-2.5 text-[13px] rounded-md outline-none transition-colors"
              style={{
                background: 'var(--bg-page)',
                border: '1px solid var(--border-soft)',
                color: 'var(--text-primary)',
              }}
              placeholder="Hỏi về định cư Canada, Mỹ, New Zealand..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              disabled={isBusy}
              onFocus={e => { (e.target as HTMLInputElement).style.borderColor = 'var(--gold)'; }}
              onBlur={e => { (e.target as HTMLInputElement).style.borderColor = 'var(--border-soft)'; }}
            />
            <button onClick={handleSend} disabled={isBusy || !input.trim()}
              aria-label="Gửi tin nhắn"
              className="w-[38px] h-[38px] rounded-md flex items-center justify-center shrink-0 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ background: 'var(--navy-deep)' }}
              onMouseEnter={e => { if (!isBusy && input.trim()) (e.currentTarget as HTMLButtonElement).style.background = 'var(--navy-mid)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--navy-deep)'; }}>
              {isBusy
                ? <span className="flex gap-0.5">
                    <span className="typing-dot w-1 h-1 rounded-full" style={{ background: 'var(--gold)' }} />
                    <span className="typing-dot w-1 h-1 rounded-full" style={{ background: 'var(--gold)' }} />
                    <span className="typing-dot w-1 h-1 rounded-full" style={{ background: 'var(--gold)' }} />
                  </span>
                : <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--gold)" strokeWidth="2">
                    <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
                  </svg>
              }
            </button>
          </div>
          <p className="text-[10.5px] text-center mt-2 tracking-wide" style={{ color: 'var(--text-faint)' }}>
            AI có thể mắc lỗi · Vui lòng xác minh với nguồn chính thức
          </p>
        </div>
      </div>
    </div>
  );
}
