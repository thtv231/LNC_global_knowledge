import { Injectable, HttpException, HttpStatus } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Observable, Subject } from 'rxjs';

export interface SseMessage {
  data: string;
}

@Injectable()
export class ChatService {
  private readonly aiServiceUrl: string;
  private readonly timeout: number;

  constructor(private config: ConfigService) {
    this.aiServiceUrl = this.config.get<string>(
      'AI_SERVICE_URL',
      'http://localhost:8000',
    );
    this.timeout = this.config.get<number>('AI_SERVICE_TIMEOUT', 60000);
  }

  async fetchNews(): Promise<{ items: unknown[] }> {
    try {
      const res = await fetch(`${this.aiServiceUrl}/news`);
      return res.json() as Promise<{ items: unknown[] }>;
    } catch {
      return { items: [] };
    }
  }

  /**
   * Proxy SSE stream từ Python FastAPI về browser.
   * Dùng native fetch + ReadableStream để không buffer toàn bộ response.
   */
  streamChat(query: string, sessionId: string): Observable<SseMessage> {
    const subject = new Subject<SseMessage>();

    const run = async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeout);

      try {
        const res = await fetch(`${this.aiServiceUrl}/chat/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, session_id: sessionId }),
          signal: controller.signal,
        });

        if (!res.ok) {
          throw new HttpException('AI service error', HttpStatus.BAD_GATEWAY);
        }

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const payload = line.slice(6).trim();
              if (payload === '[DONE]') {
                subject.complete();
                return;
              }
              subject.next({ data: payload });
            }
          }
        }
        subject.complete();
      } catch (err) {
        subject.error(err);
      } finally {
        clearTimeout(timer);
      }
    };

    void run();
    return subject.asObservable();
  }
}
