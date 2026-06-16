import { useState } from 'react';
import type { Message } from '../types/chat';
import { MarkdownText } from './MarkdownText';
import { CitationPanel } from './CitationPanel';
import { SuggestionChips } from './SuggestionChips';
import { IntakeCard } from './IntakeCard';
import { ConsultantCard } from './ConsultantCard';

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

  if (isUser) {
    return (
      <div className="flex justify-end mb-4 gap-2 items-end">
        <div className="max-w-[75%] bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm leading-relaxed shadow-sm">
          {message.content}
        </div>
        <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold shrink-0 mb-0.5">
          U
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-4 gap-2 items-start">
      {/* Avatar */}
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-sm shrink-0 mt-0.5 shadow-sm">
        🌏
      </div>

      {/* Bubble */}
      <div className="max-w-[80%] bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        {/* Web results — hiện ngay khi search xong, trước khi bot trả lời */}
        {message.webResults && message.webResults.length > 0 && (
          <div className="mb-3 rounded-xl border border-emerald-200 dark:border-emerald-800 overflow-hidden">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 dark:bg-emerald-900/30">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
              <span className="text-[10px] font-semibold text-emerald-700 dark:text-emerald-400 uppercase tracking-wide">
                Tìm kiếm web · mới nhất
              </span>
            </div>
            <div className="divide-y divide-gray-50 dark:divide-gray-700">
              {message.webResults.map((r, i) => {
                let host = r.url;
                try { host = new URL(r.url).hostname.replace('www.', ''); } catch { /* noop */ }
                return (
                  <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
                     className="flex gap-2 px-3 py-2 hover:bg-emerald-50/60 dark:hover:bg-emerald-900/10 transition-colors group">
                    <span className="shrink-0 text-[9px] font-semibold mt-0.5 px-1.5 py-0.5 h-fit rounded bg-gray-100 dark:bg-gray-700 text-gray-500">
                      {host}
                    </span>
                    <span className="text-xs text-gray-700 dark:text-gray-300 group-hover:text-emerald-700 dark:group-hover:text-emerald-400 line-clamp-2 transition-colors">
                      {r.title}
                    </span>
                  </a>
                );
              })}
            </div>
          </div>
        )}

        {message.content
          ? <MarkdownText content={message.content} isStreaming={message.isStreaming ?? false} />
          : message.isStreaming
            ? message.statusMessage
              ? <div className="flex items-center gap-2 py-0.5">
                  <svg className="animate-spin shrink-0 w-3.5 h-3.5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                  </svg>
                  <span className="text-xs text-gray-500 italic transition-all duration-300">{message.statusMessage}</span>
                </div>
              : <span className="flex gap-1 items-center h-5">
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </span>
            : null
        }
        <IntakeCard
          options={message.intake_options ?? []}
          onSelect={onSuggestionSelect}
          disabled={isLoading}
          variant="program"
        />
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
            <div className="mt-3 pt-2 border-t border-gray-100 dark:border-gray-700 space-y-1.5">
              <button
                onClick={() => setShowForm(true)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left text-sm
                           border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800
                           hover:border-[#2D9E34] hover:bg-green-50 dark:hover:bg-green-900/10
                           hover:shadow-sm transition-all duration-150 group"
              >
                <span className="shrink-0 w-6 h-6 rounded-full bg-green-100 text-green-700 text-xs
                                 flex items-center justify-center font-semibold
                                 group-hover:bg-[#2D9E34] group-hover:text-white transition-colors">1</span>
                <span className="flex-1 text-gray-700 dark:text-gray-300 group-hover:text-[#2D9E34] transition-colors">
                  ✅ Có, chuyên viên L&C liên hệ tôi trực tiếp
                </span>
                <span className="text-gray-300 group-hover:text-[#2D9E34] transition-colors">→</span>
              </button>
              <button
                onClick={() => setShowConsultant(false)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left text-sm
                           border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800
                           hover:border-[#0C3656] hover:bg-blue-50 dark:hover:bg-blue-900/20
                           hover:shadow-sm transition-all duration-150 group"
              >
                <span className="shrink-0 w-6 h-6 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 text-xs
                                 flex items-center justify-center font-semibold
                                 group-hover:bg-[#0C3656] group-hover:text-white transition-colors">2</span>
                <span className="flex-1 text-gray-700 dark:text-gray-300 group-hover:text-[#0C3656] transition-colors">
                  💬 Không, tiếp tục hỏi chatbot
                </span>
                <span className="text-gray-300 group-hover:text-[#0C3656] transition-colors">→</span>
              </button>
            </div>
          )
        )}
        <CitationPanel sources={message.sources ?? []} />
        <SuggestionChips
          suggestions={message.suggestions ?? []}
          onSelect={onSuggestionSelect}
          disabled={isLoading}
        />
      </div>
    </div>
  );
}
