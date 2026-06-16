import type { Source } from '../types/chat';

interface Props { sources: Source[] }

const COUNTRY: Record<string, { flag: string; label: string; color: string }> = {
  canada:     { flag: '🇨🇦', label: 'Canada',      color: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300' },
  usa:        { flag: '🇺🇸', label: 'Mỹ',          color: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' },
  newzealand: { flag: '🇳🇿', label: 'New Zealand', color: 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300' },
};

function hostname(url: string) {
  try { return new URL(url).hostname.replace('www.', ''); } catch { return url; }
}

export function CitationPanel({ sources }: Props) {
  if (!sources?.length) return null;

  const webSources = sources.filter(s => s.is_web);
  const kbSources  = sources.filter(s => !s.is_web);

  return (
    <div className="mt-3 pt-2.5 border-t border-gray-100 dark:border-gray-700 space-y-2.5">

      {/* Web sources */}
      {webSources.length > 0 && (
        <div>
          <p className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wide mb-1.5">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Tìm kiếm web · mới nhất
          </p>
          <div className="flex flex-col gap-1.5">
            {webSources.map((s, i) => (
              <a
                key={`web-${i}`}
                href={s.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 group"
              >
                <span className="shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                  🌐 {hostname(s.source_url)}
                </span>
                <span className="text-xs text-blue-600 dark:text-blue-400 group-hover:underline truncate">
                  {s.title || hostname(s.source_url)}
                </span>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* KB sources */}
      {kbSources.length > 0 && (
        <div>
          <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide mb-1.5">
            {webSources.length > 0 ? 'Cơ sở dữ liệu' : 'Nguồn tham khảo'}
          </p>
          <div className="flex flex-col gap-1.5">
            {kbSources.map((s, i) => {
              const c = COUNTRY[s.country] ?? { flag: '📄', label: s.country, color: 'bg-gray-100 text-gray-600' };
              return (
                <a
                  key={`kb-${i}`}
                  href={s.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 group"
                >
                  <span className={`shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded ${c.color}`}>
                    {c.flag} {c.label}
                  </span>
                  <span className="text-xs text-blue-600 dark:text-blue-400 group-hover:underline truncate">
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
