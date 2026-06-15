import { useState, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import type { Message, ChatMeta } from '../types/chat';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3000';

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef<(() => void) | null>(null);

  const sendMessage = useCallback(async (query: string) => {
    if (!query.trim() || isLoading) return;

    const userMsg: Message = { id: uuidv4(), role: 'user', content: query };
    const assistantId = uuidv4();
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    };
    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setIsLoading(true);

    let cancelled = false;
    abortRef.current = () => { cancelled = true; };

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, session_id: sessionId }),
      });

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done || cancelled) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') break;

          try {
            const event = JSON.parse(raw);

            if (event.type === 'token') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: m.content + event.content }
                  : m
              ));
            } else if (event.type === 'meta') {
              const meta = event as ChatMeta;
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, sources: meta.sources, suggestions: meta.suggestions, intake_options: meta.intake_options, profile_options: meta.profile_options, consultant_ask: meta.consultant_ask, contact_form: meta.contact_form, isStreaming: false }
                  : m
              ));
            } else if (event.type === 'error') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: `Có lỗi xảy ra: ${event.message}`, isStreaming: false }
                  : m
              ));
            }
          } catch {
            // JSON parse error — bỏ qua dòng này
          }
        }
      }
    } catch (err) {
      if (!cancelled) {
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? { ...m, content: 'Không thể kết nối đến server. Vui lòng thử lại.', isStreaming: false }
            : m
        ));
      }
    } finally {
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, isStreaming: false } : m
      ));
      setIsLoading(false);
    }
  }, [sessionId, isLoading]);

  const cancelStream = useCallback(() => {
    abortRef.current?.();
  }, []);

  return { messages, isLoading, sendMessage, cancelStream };
}
