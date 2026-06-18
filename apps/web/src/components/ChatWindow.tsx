import { useState, useRef, useEffect } from 'react';
import { MessageBubble } from './MessageBubble';
import { MarkdownText } from './MarkdownText';
import { IntakeWizard } from './IntakeWizard';
import { useChat } from '../hooks/useChat';
import { useSession } from '../hooks/useSession';

const SUGGESTIONS = [
  'Điều kiện Express Entry Canada 2024?',
  'So sánh EB2-NIW và EB1-A Mỹ',
  'Chương trình Skilled Migrant New Zealand',
  'Chi phí định cư Canada mất bao nhiêu?',
];

const WELCOME = `Xin chào! Tôi là **trợ lý AI của L&C Global** 🌏

Với hơn **12 năm kinh nghiệm** và **1.000+ hồ sơ thành công**, L&C Global đồng hành cùng Anh/Chị trên lộ trình định cư toàn cầu.

Tôi có thể tư vấn về:
- **Canada** — Express Entry, PNP, LMIA, bảo lãnh gia đình
- **Mỹ** — EB1-A, EB2-NIW, L1 Visa, Green Card
- **New Zealand** — Skilled Migrant, AEWV

Bạn muốn tìm hiểu về chương trình nào?`;

export function ChatWindow() {
  const sessionId = useSession();
  const { messages, isLoading, sendMessage } = useChat(sessionId);
  const [input, setInput] = useState('');
  const [showWizard, setShowWizard] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q || isLoading) return;
    setInput('');
    inputRef.current?.focus();
    await sendMessage(q);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-900">

      {/* ── Header ── */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-lg shadow">
            🌏
          </div>
          <div>
            <h1 className="text-sm font-bold text-gray-900 dark:text-white leading-tight">
              Tư vấn Định cư Quốc tế
            </h1>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <p className="text-[11px] text-gray-400">Canada · Mỹ · New Zealand</p>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-1 text-[11px] text-gray-400 bg-gray-50 dark:bg-gray-700 px-2.5 py-1 rounded-full border border-gray-200 dark:border-gray-600">
            <span>🤖</span>
            <span>AI Assistant</span>
          </div>
        </div>
      </div>

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6">

          {/* Welcome message */}
          {messages.length === 0 && (
            <div className="flex flex-col gap-4">
              {/* Bot welcome bubble */}
              <div className="flex justify-start gap-2 items-start">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-sm shrink-0 mt-0.5 shadow-sm">
                  🌏
                </div>
                <div className="max-w-[80%] bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                  <MarkdownText content={WELCOME} isStreaming={false} />
                </div>
              </div>

              {/* Suggestion grid */}
              <div className="ml-9 grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-xl">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => sendMessage(s)}
                    className="text-left text-sm px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700
                               bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300
                               hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20
                               hover:text-blue-700 dark:hover:text-blue-300
                               transition-all duration-150 shadow-sm"
                  >
                    <span className="text-blue-400 mr-1.5">→</span>{s}
                  </button>
                ))}
              </div>

            </div>
          )}

          {/* Message list */}
          {messages.map(msg => (
            <MessageBubble
              key={msg.id}
              message={msg}
              isLoading={isLoading}
              sessionId={sessionId}
              onSuggestionSelect={sendMessage}
            />
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── Input ── */}
      <div className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
        <div className="max-w-3xl mx-auto px-4 pt-2 pb-3">

          {/* Wizard panel — slides in above input */}
          {showWizard && (
            <div className="mb-3">
              <IntakeWizard
                onClose={() => setShowWizard(false)}
                onComplete={(summary) => {
                  setShowWizard(false);
                  sendMessage(summary);
                }}
              />
            </div>
          )}

          {/* Persistent CTA button */}
          {!showWizard && (
            <button
              onClick={() => setShowWizard(true)}
              className="w-full mb-2 flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold
                         text-white transition-all duration-150 hover:opacity-90 active:scale-[0.98]"
              style={{ backgroundColor: '#2D9E34' }}
            >
              📋 Đăng ký tư vấn chuyên sâu với L&C Global →
            </button>
          )}

          <div className="flex gap-2 items-end">
            <div className="flex-1 relative">
              <input
                ref={inputRef}
                className="w-full rounded-xl border border-gray-200 dark:border-gray-600
                           bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white
                           px-4 py-2.5 pr-10 text-sm outline-none
                           focus:ring-2 focus:ring-blue-500 focus:border-transparent
                           placeholder:text-gray-400 transition-all"
                placeholder="Hỏi về định cư Canada, Mỹ, New Zealand..."
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
                disabled={isLoading}
              />
            </div>
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="px-4 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold
                         hover:bg-blue-700 active:scale-95
                         disabled:opacity-40 disabled:cursor-not-allowed
                         transition-all duration-150 shadow-sm flex items-center gap-1.5 shrink-0"
            >
              {isLoading
                ? <span className="flex gap-1"><span className="w-1 h-1 bg-white rounded-full animate-bounce" style={{animationDelay:'0ms'}}/><span className="w-1 h-1 bg-white rounded-full animate-bounce" style={{animationDelay:'150ms'}}/><span className="w-1 h-1 bg-white rounded-full animate-bounce" style={{animationDelay:'300ms'}}/></span>
                : <>Gửi <span>↑</span></>
              }
            </button>
          </div>
          <p className="text-[10px] text-gray-400 text-center mt-1.5">
            AI có thể mắc lỗi. Vui lòng xác minh thông tin với nguồn chính thức.
          </p>
        </div>
      </div>

    </div>
  );
}
