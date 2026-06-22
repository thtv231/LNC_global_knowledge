import type { ReactNode } from 'react';

function renderInline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
  let last = 0, match: RegExpExecArray | null, i = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    if (match[2]) parts.push(<strong key={i++} className="font-semibold" style={{ color: 'var(--text-primary)' }}>{match[2]}</strong>);
    else if (match[3]) parts.push(<em key={i++} className="italic">{match[3]}</em>);
    else if (match[4]) parts.push(<code key={i++} className="px-1 py-0.5 rounded text-xs font-mono" style={{ background: 'var(--bg-page)', color: '#1d6fa4', border: '1px solid var(--border-soft)' }}>{match[4]}</code>);
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function parseTableLine(line: string): string[] {
  return line.split('|').map(c => c.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1);
}

function isTableSeparator(line: string): boolean {
  return /^\|[\s\-:|]+\|/.test(line);
}

interface TableBlock { type: 'table'; headers: string[]; rows: string[][] }
interface LineGroup { type: 'bullet' | 'ordered' | 'text'; items: string[] }
type Block = LineGroup | TableBlock;

export function MarkdownText({ content, isStreaming }: { content: string; isStreaming: boolean }) {
  const lines = content.split('\n');
  const blocks: Block[] = [];

  let i = 0;
  while (i < lines.length) {
    const raw = lines[i];

    if (raw.trimStart().startsWith('|') && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      const headers = parseTableLine(raw);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trimStart().startsWith('|')) {
        rows.push(parseTableLine(lines[i]));
        i++;
      }
      blocks.push({ type: 'table', headers, rows });
      continue;
    }

    const bulletMatch = raw.match(/^[\s]*[-*]\s+(.+)/);
    const orderedMatch = raw.match(/^[\s]*\d+\.\s+(.+)/);
    const last = blocks[blocks.length - 1];

    if (bulletMatch) {
      if (last?.type === 'bullet') (last as LineGroup).items.push(bulletMatch[1]);
      else blocks.push({ type: 'bullet', items: [bulletMatch[1]] });
    } else if (orderedMatch) {
      if (last?.type === 'ordered') (last as LineGroup).items.push(orderedMatch[1]);
      else blocks.push({ type: 'ordered', items: [orderedMatch[1]] });
    } else {
      blocks.push({ type: 'text', items: [raw] });
    }
    i++;
  }

  return (
    <div className="leading-relaxed text-sm space-y-1.5" style={{ color: 'var(--text-secondary)' }}>
      {blocks.map((g, gi) => {
        // ── Table ──────────────────────────────────────────────────
        if (g.type === 'table') {
          const t = g as TableBlock;
          return (
            <div key={gi} className="overflow-x-auto my-2 rounded-lg" style={{ border: '1px solid var(--border-main)' }}>
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr style={{ background: '#0C3656' }}>
                    {t.headers.map((h, hi) => (
                      <th key={hi} className="px-3 py-2 text-left font-semibold whitespace-nowrap" style={{ color: '#fff' }}>
                        {renderInline(h)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {t.rows.map((row, ri) => (
                    <tr key={ri} style={{ background: ri % 2 === 0 ? '#fff' : 'var(--bg-page)' }}>
                      {row.map((cell, ci) => (
                        <td key={ci} className="px-3 py-2" style={{ borderTop: '1px solid var(--border-main)', color: 'var(--text-secondary)' }}>
                          {renderInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        // ── Bullet list ────────────────────────────────────────────
        if (g.type === 'bullet') {
          return (
            <ul key={gi} className="space-y-1 my-1">
              {(g as LineGroup).items.map((item, ii) => (
                <li key={ii} className="flex gap-2">
                  <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: 'var(--navy-mid)' }} />
                  <span style={{ color: 'var(--text-secondary)' }}>{renderInline(item)}</span>
                </li>
              ))}
            </ul>
          );
        }

        // ── Ordered list ───────────────────────────────────────────
        if (g.type === 'ordered') {
          return (
            <ol key={gi} className="space-y-1 my-1">
              {(g as LineGroup).items.map((item, ii) => (
                <li key={ii} className="flex gap-2">
                  <span className="shrink-0 w-5 h-5 rounded-full text-xs flex items-center justify-center font-semibold"
                    style={{ background: 'var(--bg-page)', color: 'var(--navy-mid)', border: '1px solid var(--border-soft)' }}>
                    {ii + 1}
                  </span>
                  <span style={{ color: 'var(--text-secondary)' }}>{renderInline(item)}</span>
                </li>
              ))}
            </ol>
          );
        }

        // ── Text / headings ────────────────────────────────────────
        const line = (g as LineGroup).items[0];
        if (line.startsWith('### ')) return <h3 key={gi} className="font-bold text-sm mt-3" style={{ color: 'var(--navy-deep)' }}>{renderInline(line.slice(4))}</h3>;
        if (line.startsWith('## '))  return <h2 key={gi} className="font-bold text-base mt-3 pb-1" style={{ color: 'var(--navy-deep)', borderBottom: '1px solid var(--border-main)' }}>{renderInline(line.slice(3))}</h2>;
        if (line.startsWith('# '))   return <h1 key={gi} className="font-bold text-base mt-3" style={{ color: 'var(--navy-deep)' }}>{renderInline(line.slice(2))}</h1>;
        if (line.trim() === '---' || line.trim() === '***') return <hr key={gi} style={{ borderColor: 'var(--border-main)', margin: '8px 0' }} />;
        if (line.trim() === '') return <div key={gi} className="h-1" />;
        return <p key={gi} style={{ color: 'var(--text-secondary)' }}>{renderInline(line)}</p>;
      })}
      {isStreaming && (
        <span className="inline-block w-2 h-4 ml-0.5 animate-pulse rounded-sm" style={{ background: 'var(--navy-mid)' }} />
      )}
    </div>
  );
}
