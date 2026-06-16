export interface IntakeOption {
  label: string;
  value: string;
}

export interface WebResult {
  title: string;
  url: string;
  snippet: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  suggestions?: string[];
  intake_options?: IntakeOption[];
  profile_options?: IntakeOption[];
  consultant_ask?: boolean;
  contact_form?: boolean;
  isStreaming?: boolean;
  statusMessage?: string;
  webResults?: WebResult[];
}

export interface Source {
  title: string;
  source_url: string;
  category: string;
  country: string;
  is_web?: boolean;
}

export interface ChatMeta {
  type: 'meta';
  sources: Source[];
  suggestions: string[];
  country: string | null;
  category: string | null;
  intake_options: IntakeOption[];
  profile_options: IntakeOption[];
  consultant_ask: boolean;
  contact_form: boolean;
}
