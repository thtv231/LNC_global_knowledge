import type { ReactNode } from 'react';

function renderInline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
  let last = 0, match: RegExpExecArray | null, i = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    if (match[2]) parts.push(<strong key={i++} className="font-semibold text-gray-900 dark:text-white">{match[2]}</strong>);
    else if (match[3]) parts.push(<em key={i++} className="italic">{match[3]}</em>);
    else if (match[4]) parts.push(<code key={i++} className="px-1 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs font-mono text-blue-700 dark:text-blue-300">{match[4]}</code>);
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

    // Detect markdown table: line starts with |, next line is separator
    if (raw.trimStart().startsWith('|') && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      const headers = parseTableLine(raw);
      i += 2; // skip header + separator
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
    <div className="leading-relaxed text-sm space-y-1.5">
      {blocks.map((g, gi) => {
        // ── Table ──────────────────────────────────────────────────
        if (g.type === 'table') {
          const t = g as TableBlock;
          return (
            <div key={gi} className="overflow-x-auto my-2 rounded-lg border border-gray-200 dark:border-gray-700">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="bg-[#0C3656] text-white">
                    {t.headers.map((h, hi) => (
                      <th key={hi} className="px-3 py-2 text-left font-semibold whitespace-nowrap text-white [&_strong]:text-white">
                        {renderInline(h)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {t.rows.map((row, ri) => (
                    <tr key={ri} className={ri % 2 === 0 ? 'bg-white dark:bg-gray-800' : 'bg-gray-50 dark:bg-gray-750'}>
                      {row.map((cell, ci) => (
                        <td key={ci} className="px-3 py-2 border-t border-gray-100 dark:border-gray-700 text-gray-700 dark:text-gray-300">
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
                  <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
                  <span>{renderInline(item)}</span>
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
                  <span className="shrink-0 w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-xs flex items-center justify-center font-semibold">{ii + 1}</span>
                  <span>{renderInline(item)}</span>
                </li>
              ))}
            </ol>
          );
        }

        // ── Text / headings ────────────────────────────────────────
        const line = (g as LineGroup).items[0];
        if (line.startsWith('### ')) return <h3 key={gi} className="font-bold text-sm text-[#0C3656] dark:text-blue-300 mt-3">{renderInline(line.slice(4))}</h3>;
        if (line.startsWith('## '))  return <h2 key={gi} className="font-bold text-base text-[#0C3656] dark:text-blue-200 mt-3 pb-1 border-b border-gray-200 dark:border-gray-700">{renderInline(line.slice(3))}</h2>;
        if (line.startsWith('# '))   return <h1 key={gi} className="font-bold text-base text-[#0C3656] dark:text-white mt-3">{renderInline(line.slice(2))}</h1>;
        if (line.trim() === '---' || line.trim() === '***') return <hr key={gi} className="border-gray-200 dark:border-gray-700 my-2" />;
        if (line.trim() === '') return <div key={gi} className="h-1" />;
        return <p key={gi}>{renderInline(line)}</p>;
      })}
      {isStreaming && (
        <span className="inline-block w-2 h-4 ml-0.5 bg-blue-500 animate-pulse rounded-sm" />
      )}
    </div>
  );
}
