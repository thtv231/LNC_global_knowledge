import {
  Controller,
  Post,
  Get,
  Body,
  UsePipes,
  ValidationPipe,
  Res,
  HttpCode,
} from '@nestjs/common';
import type { Response } from 'express';
import { ChatService } from './chat.service';
import { ChatRequestDto } from './dto/chat.dto';
import { SessionService } from '../session/session.service';

@Controller('chat')
export class ChatController {
  constructor(
    private readonly chatService: ChatService,
    private readonly sessionService: SessionService,
  ) {}

  /**
   * POST /chat
   * Body: { query: string, sessionId?: string }
   * Returns SSE stream với Content-Type: text/event-stream
   */
  @Get('news')
  async latestNews() {
    return this.chatService.fetchNews();
  }

  @Post()
  @HttpCode(200)
  @UsePipes(new ValidationPipe({ whitelist: true }))
  streamChat(@Body() dto: ChatRequestDto, @Res() res: Response): void {
    const sessionId = this.sessionService.getSessionId(dto.session_id);

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    res.setHeader('X-Session-Id', sessionId);
    res.flushHeaders();

    const stream$ = this.chatService.streamChat(dto.query, sessionId);
    const sub = stream$.subscribe({
      next: (msg) => {
        res.write(`data: ${msg.data}\n\n`);
      },
      error: (err) => {
        res.write(
          `data: ${JSON.stringify({ type: 'error', message: String((err as Error).message) })}\n\n`,
        );
        res.end();
      },
      complete: () => {
        res.write('data: [DONE]\n\n');
        res.end();
      },
    });

    res.on('close', () => sub.unsubscribe());
  }
}
