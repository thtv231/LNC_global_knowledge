import { useState, useCallback, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import type { Message, ChatMeta } from '../types/chat';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3000';

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [serverError, setServerError] = useState(false);
  const abortRef = useRef<(() => void) | null>(null);

  // Load history from server on mount
  useEffect(() => {
    if (!sessionId || historyLoaded) return;
    const load = async () => {
      try {
        const res = await fetch(`${API_URL}/history/${sessionId}`);
        if (!res.ok) return;
        const data = await res.json() as { messages: { role: string; content: string }[] };
        const saved = data.messages ?? [];
        if (saved.length > 0) {
          const restored: Message[] = saved.map(m => ({
            id: uuidv4(),
            role: m.role as 'user' | 'assistant',
            content: m.content,
          }));
          setMessages(restored);
        }
      } catch {
        // silently fail — start fresh
      } finally {
        setHistoryLoaded(true);
      }
    };
    void load();
  }, [sessionId, historyLoaded]);

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

      if (res.status >= 500) {
        setServerError(true);
        setMessages(prev => prev.filter(m => m.id !== assistantId));
        return;
      }

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

            if (event.type === 'web_results') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, webResults: event.items as import('../types/chat').WebResult[] }
                  : m
              ));
            } else if (event.type === 'status') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, statusMessage: event.message as string }
                  : m
              ));
            } else if (event.type === 'token') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: m.content + (event.content as string), statusMessage: undefined }
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
            // JSON parse error — skip
          }
        }
      }
    } catch (err) {
      if (!cancelled) {
        setServerError(true);
        setMessages(prev => prev.filter(m => m.id !== assistantId && m.id !== userMsg.id));
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

  const clearHistory = useCallback(() => {
    localStorage.removeItem('chat_session_id');
    setMessages([]);
    setHistoryLoaded(false);
    window.location.reload();
  }, []);

  return { messages, isLoading, historyLoaded, serverError, setServerError, sendMessage, cancelStream, clearHistory };
}
