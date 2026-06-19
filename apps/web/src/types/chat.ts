export interface IntakeOption {
  label: string;
  value: string;
}

export interface WebResult {
  title: string;
  url: string;
  snippet: string;
}

export interface CVScores {
  eb1a_criteria_met: string[];
  eb1a_criteria_missing: string[];
  eb1a_total_met: number;
  eb1a_eligible: boolean;
  eb1a_risk_label: string;
  eb1a_risk_level: 'danger' | 'warning' | 'ok' | 'strong';
  eb2niw_prong1_score: number;
  eb2niw_prong2_score: number;
  eb2niw_prong3_score: number;
  eb2niw_total_score: number;
  eb2niw_eligible: boolean;
  eb2niw_strength_label: string;
  eb2niw_strength_level: 'weak' | 'fair' | 'good' | 'strong';
  recommended_program: string;
  experience_months: number;
}

export interface CVAnalysisData {
  profile: {
    full_name: string;
    age?: number;
    current_country?: string;
    publications: string[];
    awards: string[];
    patents: string[];
    memberships: string[];
  };
  scores: CVScores;
  similar_cases_eb1a: Record<string, unknown>[];
  similar_cases_niw: Record<string, unknown>[];
  gap_report: string;
  drive_folder_url?: string;
  processing_time_seconds: number;
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
  // CV analyzer message extensions
  cvType?: 'cv-file' | 'cv-analyzing' | 'cv-result';
  cvFile?: { name: string; size: number };
  cvData?: CVAnalysisData;
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
