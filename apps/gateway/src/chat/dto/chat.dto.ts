import { IsString, IsNotEmpty, IsOptional, MaxLength } from 'class-validator';

export class ChatRequestDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(500)
  query: string;

  @IsString()
  @IsOptional()
  session_id?: string;
}
