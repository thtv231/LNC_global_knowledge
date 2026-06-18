import { useState } from 'react';
import type { CVAnalysisData } from '../types/chat';
import { MarkdownText } from './MarkdownText';
import { ScoreCard } from './analysis/ScoreCard';
import { CitationInput } from './analysis/CitationInput';
import { ActionChips } from './analysis/ActionChips';
import type { RiskLevel } from './analysis/ScoreCard';

interface Props {
  data: CVAnalysisData;
  onAction: (text: string) => void;
}

function parseReport(raw: string): { thinking: string; report: string } {
  const m = raw.match(/<lawyer_thinking>([\s\S]*?)<\/lawyer_thinking>/);
  const thinking = m ? m[1].trim() : '';
  const report = raw.replace(/<lawyer_thinking>[\s\S]*?<\/lawyer_thinking>/, '').trim();
  return { thinking, report };
}

// Map backend risk levels → ScoreCard RiskLevel
function toRiskLevel(level: string): RiskLevel {
  if (level === 'danger') return 'danger';
  if (level === 'warning') return 'warn';
  if (level === 'ok') return 'ok';
  if (level === 'strong') return 'strong';
  return 'neutral';
}
function toStrengthLevel(level: string): RiskLevel {
  if (level === 'weak') return 'danger';
  if (level === 'fair') return 'warn';
  if (level === 'good') return 'ok';
  if (level === 'strong') return 'strong';
  return 'neutral';
}

const FOLLOW_UPS = [
  'Diện EB-2 NIW cần chuẩn bị bao nhiêu Thư giới thiệu và xin của ai?',
  'Tôi là Bác sĩ lâm sàng, làm sao chứng minh công việc có Tầm quan trọng quốc gia với Mỹ?',
  'Lộ trình tăng số bài báo quốc tế từ 2 lên 6 bài trong 6 tháng?',
];

export function CVResultBubble({ data, onAction }: Props) {
  const [showReport, setShowReport] = useState(false);
  const [showThinking, setShowThinking] = useState(false);
  const { scores, profile } = data;
  const { thinking, report } = parseReport(data.gap_report);
  const hasPublications = profile.publications.length > 0;

  const eb1aScore = {
    label: 'EB-1A',
    score: scores.eb1a_total_met,
    maxScore: 10,
    riskText: scores.eb1a_risk_label || (scores.eb1a_eligible ? 'Đủ điều kiện nộp' : 'Chưa đủ điều kiện'),
    riskLevel: toRiskLevel(scores.eb1a_risk_level),
    recommended: scores.recommended_program?.includes('EB-1A'),
  };

  const eb2Score = {
    label: 'EB-2 NIW',
    score: scores.eb2niw_total_score,
    maxScore: 9,
    riskText: scores.eb2niw_strength_label || (scores.eb2niw_eligible ? 'Khả thi' : 'Cần cải thiện'),
    riskLevel: toStrengthLevel(scores.eb2niw_strength_level),
    recommended: scores.recommended_program?.includes('NIW') || scores.recommended_program === 'Both',
  };

  return (
    <div className="flex justify-start mb-4 gap-2.5 items-start msg-enter">
      {/* Avatar */}
      <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 font-semibold text-[11px] tracking-wide"
        style={{ background: 'var(--navy-deep)', color: 'var(--gold)', border: '1px solid var(--navy-mid)' }}>
        L&C
      </div>

      <div className="max-w-[88%] rounded-2xl rounded-tl-sm px-5 py-4 space-y-3"
        style={{ background: '#FFFFFF', border: '1px solid var(--border-main)' }}>

        {/* Status header */}
        <div className="flex items-center gap-2 px-3 py-2 rounded-md"
          style={{ background: 'var(--risk-ok-bg)', border: '1px solid var(--risk-ok-border)' }}>
          <span className="w-[7px] h-[7px] rounded-full shrink-0" style={{ background: 'var(--risk-ok)' }} />
          <span className="text-[12px] font-medium" style={{ color: 'var(--risk-ok)' }}>
            Phân tích hồ sơ hoàn tất · {data.processing_time_seconds}s
          </span>
        </div>

        {/* Score cards — RingGauge */}
        <div className="grid grid-cols-2 gap-3">
          <ScoreCard data={eb1aScore} />
          <ScoreCard data={eb2Score} />
        </div>

        {/* Recommendation line */}
        <p className="text-[13px]" style={{ color: 'var(--text-secondary)' }}>
          Khuyến nghị:{' '}
          <strong style={{ color: 'var(--navy-deep)' }}>{scores.recommended_program}</strong>
          {' · '}{scores.experience_months} tháng kinh nghiệm
        </p>

        {/* Citation input */}
        {hasPublications && (
          <CitationInput onSubmit={url => onAction(`Cập nhật Google Scholar: ${url} — Hãy phân tích citations và cập nhật điểm.`)} />
        )}

        {/* Action chips */}
        <ActionChips
          actions={['Xem báo cáo đầy đủ', 'Tư duy phân tích', 'Viết thư Reviewer']}
          onAction={action => {
            if (action === 'Xem báo cáo đầy đủ') setShowReport(v => !v);
            else if (action === 'Tư duy phân tích') setShowThinking(v => !v);
            else onAction('Hãy viết thư mẫu xin làm Peer Reviewer cho một tạp chí quốc tế ISI/Scopus phù hợp với chuyên ngành trong CV.');
          }}
        />

        {/* Lawyer thinking */}
        {showThinking && thinking && (
          <div className="rounded-lg p-3" style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>
            <p className="text-[11px] font-semibold uppercase tracking-widest mb-2" style={{ color: '#92400E' }}>
              Tư duy phân tích — Luật sư AI (CoT)
            </p>
            <div className="text-[12px] leading-relaxed" style={{ color: '#78350F' }}>
              <MarkdownText content={thinking} isStreaming={false} />
            </div>
          </div>
        )}

        {/* Full gap report */}
        {showReport && (
          <div className="pt-3" style={{ borderTop: '1px solid var(--border-main)' }}>
            <MarkdownText content={report} isStreaming={false} />
          </div>
        )}

        {/* CTA */}
        <div className="rounded-lg p-3" style={{ background: 'var(--bg-muted)', border: '1px solid var(--border-main)' }}>
          <p className="text-[12px] mb-2 leading-snug" style={{ color: 'var(--text-secondary)' }}>
            Hồ sơ có tiềm năng ở diện <strong style={{ color: 'var(--navy-deep)' }}>EB-2 NIW</strong> nếu được định hướng đúng chiến lược.
          </p>
          <button
            onClick={() => onAction('Tôi muốn đặt lịch tư vấn chuyên sâu về hồ sơ EB-2 NIW với chuyên viên L&C Global.')}
            className="w-full py-2 rounded-md text-[12px] font-semibold transition-opacity hover:opacity-90"
            style={{ background: 'var(--navy-deep)', color: 'var(--gold)' }}>
            Đặt lịch 15 phút với Chuyên viên di trú →
          </button>
        </div>

        {/* Follow-up suggestions */}
        <div className="pt-1 space-y-1.5">
          <p className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            Câu hỏi gợi ý
          </p>
          {FOLLOW_UPS.map((q, i) => (
            <button key={i} onClick={() => onAction(q)}
              className="w-full text-left text-[12.5px] px-3 py-2 rounded-md transition-colors"
              style={{ border: '1px solid var(--border-soft)', background: 'var(--bg-page)', color: 'var(--text-secondary)' }}
              onMouseEnter={e => { const el = e.currentTarget as HTMLButtonElement; el.style.borderColor = 'var(--gold-border)'; el.style.background = 'var(--bg-muted)'; }}
              onMouseLeave={e => { const el = e.currentTarget as HTMLButtonElement; el.style.borderColor = 'var(--border-soft)'; el.style.background = 'var(--bg-page)'; }}>
              <span className="font-semibold mr-1.5" style={{ color: 'var(--gold)' }}>→</span>{q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
