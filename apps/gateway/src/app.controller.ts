import { Controller, Get, Post, Body, HttpCode, Param } from '@nestjs/common';
import { AppService } from './app.service';
import { ChatService } from './chat/chat.service';

@Controller()
export class AppController {
  constructor(
    private readonly appService: AppService,
    private readonly chatService: ChatService,
  ) {}

  @Get()
  getHello(): string {
    return this.appService.getHello();
  }

  @Post('intake')
  @HttpCode(200)
  async submitIntake(@Body() body: Record<string, unknown>) {
    return this.chatService.submitIntake(body);
  }

  @Get('history/:sessionId')
  async getHistory(@Param('sessionId') sessionId: string) {
    return this.chatService.getHistory(sessionId);
  }
}
