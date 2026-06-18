import { useRef } from 'react';

const ALLOWED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];

interface Props {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

export function CVUploadButton({ onFileSelect, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!ALLOWED_TYPES.includes(file.type)) {
      alert('Chỉ chấp nhận PDF hoặc Word (.docx)');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      alert('File vượt quá 10MB');
      return;
    }
    onFileSelect(file);
    e.target.value = '';
  };

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        title="Upload CV PDF/DOCX để phân tích EB-1A / EB-2 NIW"
        aria-label="Upload CV để phân tích"
        className="flex items-center justify-center w-[38px] h-[38px] rounded-md shrink-0 transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
        style={{
          background: 'var(--gold-light)',
          border: '1px solid var(--gold-border)',
          color: 'var(--gold)',
        }}
        onMouseEnter={e => {
          if (!disabled) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(201,169,110,0.25)';
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLButtonElement).style.background = 'var(--gold-light)';
        }}
      >
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="12" y1="18" x2="12" y2="12"/>
          <line x1="9" y1="15" x2="15" y2="15"/>
        </svg>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx"
        onChange={handleChange}
        style={{ display: 'none' }}
      />
    </>
  );
}
