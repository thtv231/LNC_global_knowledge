import { useState } from 'react';

// ── Step definitions ────────────────────────────────────────────────────────

interface WizardOption {
  label: string;
  value: string;
  next: string;
  isCustom?: boolean;
}

interface WizardStep {
  id: string;
  title: string;
  question: string;
  options: WizardOption[];
}

const STEPS: Record<string, WizardStep> = {
  country: {
    id: 'country', title: 'Quốc gia', question: 'Anh/Chị muốn định cư quốc gia nào?',
    options: [
      { label: '🇨🇦 Canada',                 value: 'Canada',      next: 'program_canada' },
      { label: '🇺🇸 Mỹ (USA)',               value: 'USA',         next: 'program_usa' },
      { label: '🇳🇿 New Zealand',             value: 'New Zealand', next: 'program_nz' },
      { label: '✏️ Nhập yêu cầu của Anh/Chị', value: '',            next: 'done', isCustom: true },
    ],
  },

  program_canada: {
    id: 'program_canada', title: 'Chương trình', question: 'Chương trình nào Anh/Chị quan tâm?',
    options: [
      { label: '✈️ Express Entry (FSW / CEC)',  value: 'Express Entry',            next: 'field' },
      { label: '🏙️ PNP – Định cư tỉnh bang',    value: 'PNP',                      next: 'field' },
      { label: '📋 LMIA / Work Permit',           value: 'LMIA',                     next: 'field' },
      { label: '👨‍👩‍👧 Bảo lãnh gia đình',           value: 'Bảo lãnh gia đình Canada', next: 'done' },
      { label: '✏️ Nhập yêu cầu của Anh/Chị',   value: '',                          next: 'done', isCustom: true },
    ],
  },
  program_usa: {
    id: 'program_usa', title: 'Chương trình', question: 'Chương trình nào Anh/Chị quan tâm?',
    options: [
      { label: '🔬 EB-2 NIW – Miễn yêu cầu việc làm', value: 'EB-2 NIW',  next: 'field' },
      { label: '🏆 EB-1A – Tài năng đặc biệt',          value: 'EB-1A',    next: 'field' },
      { label: '💼 H-1B – Lao động chuyên môn',          value: 'H-1B',     next: 'field' },
      { label: '🏢 L-1 – Chuyển nhượng nội bộ',          value: 'L-1 Visa', next: 'field' },
      { label: '✏️ Nhập yêu cầu của Anh/Chị',           value: '',          next: 'done', isCustom: true },
    ],
  },
  program_nz: {
    id: 'program_nz', title: 'Chương trình', question: 'Chương trình nào Anh/Chị quan tâm?',
    options: [
      { label: '⭐ Skilled Migrant Category',     value: 'Skilled Migrant', next: 'field' },
      { label: '🏭 AEWV – Accredited Employer',   value: 'AEWV',            next: 'field' },
      { label: '💰 Investor Visa',                 value: 'Investor NZ',     next: 'done' },
      { label: '🎓 Student Visa',                  value: 'Student NZ',      next: 'education' },
      { label: '✏️ Nhập yêu cầu của Anh/Chị',    value: '',                 next: 'done', isCustom: true },
    ],
  },

  field: {
    id: 'field', title: 'Ngành nghề', question: 'Ngành nghề / lĩnh vực của Anh/Chị?',
    options: [
      { label: '💻 IT / Công nghệ / Phần mềm',      value: 'IT/Công nghệ',         next: 'education' },
      { label: '⚙️ Kỹ thuật / Xây dựng',             value: 'Kỹ thuật/Xây dựng',   next: 'education' },
      { label: '🏥 Y tế / Dược / Điều dưỡng',         value: 'Y tế/Dược',            next: 'education' },
      { label: '💰 Kinh tế / Tài chính / Kế toán',    value: 'Kinh tế/Tài chính',   next: 'education' },
      { label: '🔬 Khoa học / Nghiên cứu',             value: 'Khoa học/Nghiên cứu', next: 'education' },
      { label: '✏️ Ngành khác – nhập tên ngành',      value: '',                     next: 'education', isCustom: true },
    ],
  },

  education: {
    id: 'education', title: 'Học vấn', question: 'Trình độ học vấn cao nhất của Anh/Chị?',
    options: [
      { label: '🎓 Tiến sĩ (PhD)',                 value: 'Tiến sĩ',                  next: 'experience' },
      { label: '🎓 Thạc sĩ (Master\'s)',            value: 'Thạc sĩ',                  next: 'experience' },
      { label: '🎓 Cử nhân 4 năm (Bachelor\'s)',   value: 'Cử nhân 4 năm',            next: 'experience' },
      { label: '🎓 Cử nhân 3 năm / Cao đẳng',      value: 'Cao đẳng/Cử nhân 3 năm',  next: 'experience' },
      { label: '📚 Trung cấp / Chứng chỉ nghề',    value: 'Trung cấp',                next: 'experience' },
      { label: '✏️ Khác – nhập trình độ cụ thể',   value: '',                         next: 'experience', isCustom: true },
    ],
  },

  experience: {
    id: 'experience', title: 'Kinh nghiệm', question: 'Số năm kinh nghiệm làm việc trong ngành?',
    options: [
      { label: '⏱️ Dưới 1 năm',   value: '<1 năm',   next: 'language' },
      { label: '📅 1 – 3 năm',    value: '1-3 năm',  next: 'language' },
      { label: '📅 3 – 5 năm',    value: '3-5 năm',  next: 'language' },
      { label: '📅 5 – 10 năm',   value: '5-10 năm', next: 'language' },
      { label: '📅 Trên 10 năm',  value: '>10 năm',  next: 'language' },
      { label: '✏️ Nhập số năm cụ thể', value: '',   next: 'language', isCustom: true },
    ],
  },

  language: {
    id: 'language', title: 'Tiếng Anh', question: 'Trình độ tiếng Anh hiện tại (IELTS General)?',
    options: [
      { label: '🌟 IELTS 7.5+ (CLB 10+)',      value: 'IELTS 7.5+',      next: 'age' },
      { label: '✅ IELTS 6.5 – 7.0 (CLB 9)',   value: 'IELTS 6.5-7.0',  next: 'age' },
      { label: '✅ IELTS 6.0 (CLB 7)',           value: 'IELTS 6.0',      next: 'age' },
      { label: '⚠️ Dưới 6.0 / Chưa thi IELTS', value: 'Chưa thi / <6.0', next: 'age' },
      { label: '✏️ Nhập điểm IELTS / CELPIP / TEF cụ thể', value: '', next: 'age', isCustom: true },
    ],
  },

  age: {
    id: 'age', title: 'Độ tuổi', question: 'Anh/Chị hiện bao nhiêu tuổi?',
    options: [
      { label: '🟢 Dưới 25 tuổi', value: '<25',   next: 'done' },
      { label: '🟢 25 – 29 tuổi', value: '25-29', next: 'done' },
      { label: '🟢 30 – 35 tuổi', value: '30-35', next: 'done' },
      { label: '🟡 36 – 40 tuổi', value: '36-40', next: 'done' },
      { label: '🟠 41 – 45 tuổi', value: '41-45', next: 'done' },
      { label: '🔴 Trên 45 tuổi', value: '>45',   next: 'done' },
      { label: '✏️ Nhập tuổi cụ thể', value: '',  next: 'done', isCustom: true },
    ],
  },
};

// ── Component ────────────────────────────────────────────────────────────────

interface Props {
  onClose: () => void;
  onComplete: (summary: string) => void;
}

export function IntakeWizard({ onClose, onComplete }: Props) {
  const [stepId, setStepId] = useState<string>('country');
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [customText, setCustomText] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);

  const step = STEPS[stepId];

  const totalSteps = 7;
  const progress = Math.min(Object.keys(answers).length / totalSteps, 1);

  const buildSummary = (ans: Record<string, string>) => {
    const lines = Object.entries(ans).map(([k, v]) => `${STEPS[k]?.title ?? k}: ${v}`);
    return `📋 Đăng ký tư vấn chuyên sâu:\n${lines.join('\n')}`;
  };

  const handleOption = (opt: WizardOption) => {
    if (opt.isCustom) {
      setShowCustomInput(true);
      return;
    }
    const newAnswers = { ...answers, [stepId]: opt.value };
    setAnswers(newAnswers);
    if (opt.next === 'done') {
      onComplete(buildSummary(newAnswers));
    } else {
      setStepId(opt.next);
    }
  };

  const handleCustomSubmit = () => {
    if (!customText.trim()) return;
    const newAnswers = { ...answers, [stepId]: customText.trim() };
    const nextId = STEPS[stepId]?.options.find(o => o.isCustom)?.next ?? 'done';
    setAnswers(newAnswers);
    setShowCustomInput(false);
    setCustomText('');
    if (nextId === 'done') {
      onComplete(buildSummary(newAnswers));
    } else {
      setStepId(nextId);
    }
  };

  const handleBack = () => {
    const keys = Object.keys(answers);
    if (!keys.length) return;
    const prevKey = keys[keys.length - 1];
    const newAnswers = { ...answers };
    delete newAnswers[prevKey];
    setAnswers(newAnswers);
    setShowCustomInput(false);
    setCustomText('');
    setStepId(prevKey);
  };

  const labelForKey = (key: string) => {
    if (key.startsWith('program')) return 'Chương trình';
    return STEPS[key]?.title ?? key;
  };

  return (
    <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden shadow-sm">

      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between" style={{ backgroundColor: '#0C3656' }}>
        <div>
          <p className="text-xs text-blue-200 font-medium uppercase tracking-wide">Đăng ký tư vấn chuyên sâu</p>
          <p className="text-white text-sm font-semibold">L&C Global — Lawful Steps · Confident Future</p>
        </div>
        <button onClick={onClose} className="text-blue-300 hover:text-white text-lg transition-colors">✕</button>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-gray-100 dark:bg-gray-700">
        <div className="h-1 transition-all duration-500" style={{ width: `${progress * 100}%`, backgroundColor: '#2D9E34' }} />
      </div>

      {/* Breadcrumb */}
      {Object.keys(answers).length > 0 && (
        <div className="px-4 pt-3 flex flex-wrap gap-1.5">
          {Object.entries(answers).map(([key, val]) => (
            <span key={key} className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
              {labelForKey(key)}: <strong className="text-gray-700 dark:text-gray-300">{val}</strong>
            </span>
          ))}
        </div>
      )}

      {/* Body */}
      <div className="px-4 py-4">
        {showCustomInput ? (
          <div className="space-y-3">
            <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">
              Anh/Chị mô tả ngắn gọn nhu cầu định cư của mình:
            </p>
            <textarea
              autoFocus
              rows={4}
              value={customText}
              onChange={e => setCustomText(e.target.value)}
              placeholder="Ví dụ: Tôi 32 tuổi, kỹ sư IT, muốn định cư Canada cho cả gia đình, IELTS 6.5, hiện đang ở Việt Nam..."
              className="w-full text-sm rounded-xl border border-gray-200 dark:border-gray-600
                         bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-white
                         px-3 py-2.5 outline-none resize-none
                         focus:ring-2 focus:ring-[#0C3656] focus:border-transparent"
              onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) handleCustomSubmit(); }}
            />
            <div className="flex gap-2">
              <button
                onClick={() => { setShowCustomInput(false); setCustomText(''); }}
                className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm text-gray-500 hover:bg-gray-50 transition-colors">
                ← Quay lại
              </button>
              <button
                onClick={handleCustomSubmit}
                disabled={!customText.trim()}
                className="flex-1 py-2.5 rounded-xl text-white text-sm font-semibold transition-all
                           disabled:opacity-40 hover:opacity-90"
                style={{ backgroundColor: '#0C3656' }}>
                Tiếp theo →
              </button>
            </div>
            <p className="text-[10px] text-gray-400 text-center">Ctrl+Enter để tiếp theo</p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">{step?.question}</p>
            <div className="space-y-1.5">
              {step?.options.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => handleOption(opt)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left text-sm
                             border bg-white dark:bg-gray-800
                             hover:shadow-sm transition-all duration-150 group
                             ${opt.isCustom
                               ? 'border-dashed border-gray-300 dark:border-gray-600 hover:border-[#2D9E34] hover:bg-green-50 dark:hover:bg-green-900/10'
                               : 'border-gray-200 dark:border-gray-700 hover:border-[#0C3656] hover:bg-blue-50 dark:hover:bg-blue-900/20'
                             }`}
                >
                  <span className={`shrink-0 w-6 h-6 rounded-full text-xs flex items-center justify-center font-semibold transition-colors
                                   ${opt.isCustom
                                     ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 group-hover:bg-[#2D9E34] group-hover:text-white'
                                     : 'bg-gray-100 dark:bg-gray-700 text-gray-500 group-hover:bg-[#0C3656] group-hover:text-white'
                                   }`}>
                    {i + 1}
                  </span>
                  <span className={`flex-1 transition-colors
                                   ${opt.isCustom
                                     ? 'text-gray-500 dark:text-gray-400 group-hover:text-[#2D9E34]'
                                     : 'text-gray-700 dark:text-gray-300 group-hover:text-[#0C3656] dark:group-hover:text-blue-300'
                                   }`}>
                    {opt.label}
                  </span>
                  <span className={`transition-colors text-base
                                   ${opt.isCustom ? 'text-gray-300 group-hover:text-[#2D9E34]' : 'text-gray-300 group-hover:text-[#0C3656]'}`}>
                    {opt.isCustom ? '✏️' : '→'}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Back button */}
      {Object.keys(answers).length > 0 && (
        <div className="px-4 pb-3">
          <button onClick={handleBack} className="text-xs text-gray-400 hover:text-gray-600 transition-colors flex items-center gap-1">
            ← Quay lại
          </button>
        </div>
      )}
    </div>
  );
}
