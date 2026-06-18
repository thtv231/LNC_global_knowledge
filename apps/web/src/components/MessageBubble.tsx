import { useState } from 'react';
import type { Message } from '../types/chat';
import { MarkdownText } from './MarkdownText';
import { CitationPanel } from './CitationPanel';
import { SuggestionChips } from './SuggestionChips';
import { IntakeCard } from './IntakeCard';
import { ConsultantCard } from './ConsultantCard';

interface Props {
  message: Message;
  isLoading: boolean;
  sessionId: string;
  onSuggestionSelect: (q: string) => void;
}

export function MessageBubble({ message, isLoading, sessionId, onSuggestionSelect }: Props) {
  const [showConsultant, setShowConsultant] = useState(true);
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
        {message.content
          ? <MarkdownText content={message.content} isStreaming={message.isStreaming ?? false} />
          : message.isStreaming
            ? <span className="flex gap-1 items-center h-5">
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
          <ConsultantCard
            profileSummary={message.content}
            sessionId={sessionId}
            startAtForm={message.contact_form}
            onContinueChat={() => setShowConsultant(false)}
          />
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
