import { useState, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3000';

interface NewsItem {
  title: string;
  url: string;
  snippet: string;
}

function hostname(url: string) {
  try { return new URL(url).hostname.replace('www.', ''); } catch { return url; }
}

export function LiveNewsPanel() {
  const [items, setItems]   = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/chat/news`)
      .then(r => r.json())
      .then((d: { items: NewsItem[] }) => setItems(d.items ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  if (!loading && items.length === 0) return null;

  return (
    <div className="ml-9 mt-3 rounded-2xl border border-emerald-200 dark:border-emerald-800 bg-white dark:bg-gray-800 shadow-sm overflow-hidden max-w-xl">
      {/* Header */}
      <div className="flex items-center gap-2 px-3.5 py-2.5 bg-emerald-50 dark:bg-emerald-900/30 border-b border-emerald-100 dark:border-emerald-800">
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
        <span className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 uppercase tracking-wide">
          Tin tức nhập cư · mới nhất
        </span>
        <span className="ml-auto text-[10px] text-emerald-500 dark:text-emerald-500">🌐 Tavily Search</span>
      </div>

      {/* Content */}
      <div className="divide-y divide-gray-50 dark:divide-gray-700">
        {loading
          ? Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="px-3.5 py-2.5 space-y-1.5 animate-pulse">
                <div className="h-3 bg-gray-100 dark:bg-gray-700 rounded w-3/4" />
                <div className="h-2.5 bg-gray-100 dark:bg-gray-700 rounded w-full" />
              </div>
            ))
          : items.map((item, i) => (
              <a
                key={i}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex flex-col px-3.5 py-2.5 hover:bg-emerald-50/50 dark:hover:bg-emerald-900/10 transition-colors group"
              >
                <div className="flex items-start gap-2">
                  <span className="shrink-0 mt-0.5 text-[9px] font-semibold px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
                    {hostname(item.url)}
                  </span>
                  <span className="text-xs font-medium text-gray-800 dark:text-gray-200 group-hover:text-emerald-700 dark:group-hover:text-emerald-400 transition-colors leading-tight line-clamp-2">
                    {item.title}
                  </span>
                </div>
                {item.snippet && (
                  <p className="mt-1 text-[11px] text-gray-400 dark:text-gray-500 line-clamp-2 pl-0">
                    {item.snippet}
                  </p>
                )}
              </a>
            ))
        }
      </div>
    </div>
  );
}
