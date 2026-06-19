import {
  Controller,
  Post,
  UploadedFile,
  UseInterceptors,
  HttpException,
  HttpStatus,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { ConfigService } from '@nestjs/config';

@Controller('cv')
export class CvController {
  private readonly aiServiceUrl: string;

  constructor(private config: ConfigService) {
    this.aiServiceUrl = this.config.get<string>(
      'AI_SERVICE_URL',
      'http://localhost:8000',
    );
  }

  @Post('analyze')
  @UseInterceptors(FileInterceptor('file', { limits: { fileSize: 10 * 1024 * 1024 } }))
  async analyzeCV(
    @UploadedFile() file: Express.Multer.File,
  ): Promise<unknown> {
    if (!file) {
      throw new HttpException('File is required', HttpStatus.BAD_REQUEST);
    }

    const formData = new FormData();
    const blob = new Blob([new Uint8Array(file.buffer)], { type: file.mimetype });
    formData.append('file', blob, file.originalname);

    const res = await fetch(`${this.aiServiceUrl}/cv/analyze`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const text = await res.text();
      throw new HttpException(text || 'CV analyze failed', res.status);
    }

    return res.json();
  }
}
