import type { Source } from '../types/chat';

interface Props { sources: Source[] }

const COUNTRY: Record<string, { label: string; bg: string; color: string }> = {
  canada:     { label: 'Canada',      bg: '#FEF2F2', color: '#991B1B' },
  usa:        { label: 'Mỹ',          bg: '#EFF6FF', color: '#1E40AF' },
  newzealand: { label: 'New Zealand', bg: '#F0FDF4', color: '#065F46' },
};

function hostname(url: string) {
  try { return new URL(url).hostname.replace('www.', ''); } catch { return url; }
}

export function CitationPanel({ sources }: Props) {
  if (!sources?.length) return null;

  const webSources = sources.filter(s => s.is_web);
  const kbSources  = sources.filter(s => !s.is_web);

  return (
    <div className="mt-3 pt-3 space-y-2.5" style={{ borderTop: '1px solid var(--c-border)' }}>

      {webSources.length > 0 && (
        <div>
          <p className="flex items-center gap-1.5 mb-1.5" style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#065F46' }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--c-green)' }} />
            Tìm kiếm web · mới nhất
          </p>
          <div className="flex flex-col gap-1.5">
            {webSources.map((s, i) => (
              <a key={`web-${i}`} href={s.source_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 no-underline group">
                <span className="shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded"
                  style={{ background: '#F0FDF4', color: '#065F46', border: '1px solid #D1FAE5' }}>
                  {hostname(s.source_url)}
                </span>
                <span className="text-xs truncate group-hover:underline" style={{ color: 'var(--c-blue)' }}>
                  {s.title || hostname(s.source_url)}
                </span>
              </a>
            ))}
          </div>
        </div>
      )}

      {kbSources.length > 0 && (
        <div>
          <p className="mb-1.5" style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--c-text-3)' }}>
            {webSources.length > 0 ? 'Cơ sở dữ liệu' : 'Nguồn tham khảo'}
          </p>
          <div className="flex flex-col gap-1.5">
            {kbSources.map((s, i) => {
              const c = COUNTRY[s.country] ?? { label: s.country, bg: 'var(--c-surface)', color: 'var(--c-text-3)' };
              return (
                <a key={`kb-${i}`} href={s.source_url} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-2 no-underline group">
                  <span className="shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded"
                    style={{ background: c.bg, color: c.color, border: `1px solid ${c.bg}` }}>
                    {c.label}
                  </span>
                  <span className="text-xs truncate group-hover:underline" style={{ color: 'var(--c-blue)' }}>
                    {s.title || hostname(s.source_url)}
                  </span>
                </a>
              );
            })}
          </div>
        </div>
      )}

    </div>
  );
}
