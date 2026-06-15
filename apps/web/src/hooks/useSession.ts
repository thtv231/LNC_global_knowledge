import { useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

export function useSession(): string {
  const [sessionId] = useState<string>(() => {
    const existing = sessionStorage.getItem('chat_session_id');
    if (existing) return existing;
    const newId = uuidv4();
    sessionStorage.setItem('chat_session_id', newId);
    return newId;
  });
  return sessionId;
}
