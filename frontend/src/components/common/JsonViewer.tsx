// frontend/src/components/common/JsonViewer.tsx
import { useState, useCallback, useMemo } from "react";
import clsx from "clsx";

interface JsonViewerProps {
  /** Raw content string to display. */
  content: string;
  /** Language hint for syntax coloring: "json", "hcl", "bicep", or undefined. */
  language?: string;
  /** Max height CSS class. Defaults to "max-h-96". */
  maxHeight?: string;
}

/** Simple regex-based token types for coloring. */
type TokenType = "key" | "string" | "number" | "boolean" | "null" | "plain";

const TOKEN_COLORS: Record<TokenType, string> = {
  key: "text-blue-400",
  string: "text-emerald-400",
  number: "text-amber-400",
  boolean: "text-purple-400",
  null: "text-slate-500",
  plain: "text-slate-300",
};

/**
 * Colorize a single line of JSON using simple regex matching.
 * Returns an array of JSX spans with appropriate color classes.
 */
function colorizeJson(line: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Match JSON tokens: keys (string followed by :), strings, numbers, booleans, null
  const tokenRegex =
    /("(?:[^"\\]|\\.)*")\s*:|("(?:[^"\\]|\\.)*")|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b|(true|false)\b|(null)\b/g;

  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenRegex.exec(line)) !== null) {
    // Add plain text before this match
    if (match.index > lastIndex) {
      parts.push(
        <span key={`p-${lastIndex}`} className={TOKEN_COLORS.plain}>
          {line.slice(lastIndex, match.index)}
        </span>,
      );
    }

    if (match[1] !== undefined) {
      // Key
      parts.push(
        <span key={`k-${match.index}`} className={TOKEN_COLORS.key}>
          {match[1]}
        </span>,
      );
      // Add the colon
      const colonStart = match.index + match[1].length;
      const colonPart = line.slice(colonStart, match.index + match[0].length);
      parts.push(
        <span key={`c-${match.index}`} className={TOKEN_COLORS.plain}>
          {colonPart}
        </span>,
      );
    } else if (match[2] !== undefined) {
      // String value
      parts.push(
        <span key={`s-${match.index}`} className={TOKEN_COLORS.string}>
          {match[2]}
        </span>,
      );
    } else if (match[3] !== undefined) {
      // Number
      parts.push(
        <span key={`n-${match.index}`} className={TOKEN_COLORS.number}>
          {match[3]}
        </span>,
      );
    } else if (match[4] !== undefined) {
      // Boolean
      parts.push(
        <span key={`b-${match.index}`} className={TOKEN_COLORS.boolean}>
          {match[4]}
        </span>,
      );
    } else if (match[5] !== undefined) {
      // Null
      parts.push(
        <span key={`nl-${match.index}`} className={TOKEN_COLORS.null}>
          {match[5]}
        </span>,
      );
    }

    lastIndex = match.index + match[0].length;
  }

  // Remaining text
  if (lastIndex < line.length) {
    parts.push(
      <span key={`r-${lastIndex}`} className={TOKEN_COLORS.plain}>
        {line.slice(lastIndex)}
      </span>,
    );
  }

  return parts.length > 0
    ? parts
    : [
        <span key="full" className={TOKEN_COLORS.plain}>
          {line}
        </span>,
      ];
}

/**
 * Generic JSON/code viewer with line numbers, copy button,
 * and simple regex-based syntax highlighting.
 *
 * Usage:
 * ```tsx
 * <JsonViewer content={JSON.stringify(data, null, 2)} language="json" />
 * ```
 */
export function JsonViewer({
  content,
  language,
  maxHeight = "max-h-96",
}: JsonViewerProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [content]);

  const lines = useMemo(() => content.split("\n"), [content]);
  const lineNumberWidth = String(lines.length).length;
  const isJson = language === "json" || (!language && content.trimStart().startsWith("{"));

  return (
    <div className="relative rounded-xl border border-slate-700/80 bg-slate-900">
      {/* Copy button */}
      <button
        onClick={handleCopy}
        className="absolute right-2 top-2 z-10 rounded-lg border border-slate-600 bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
      >
        {copied ? "Copied!" : "Copy"}
      </button>

      {/* Language tag */}
      {language && (
        <div className="absolute left-3 top-2 text-[10px] font-medium uppercase tracking-wider text-slate-500">
          {language}
        </div>
      )}

      <div
        className={clsx(
          "overflow-auto p-4 pt-8 font-mono text-sm leading-relaxed",
          maxHeight,
        )}
      >
        <table className="w-full border-collapse">
          <tbody>
            {lines.map((line, idx) => (
              <tr key={idx} className="hover:bg-slate-800/50">
                <td
                  className="select-none pr-4 text-right text-slate-600"
                  style={{ minWidth: `${lineNumberWidth + 1}ch` }}
                >
                  {idx + 1}
                </td>
                <td className="whitespace-pre">
                  {isJson ? colorizeJson(line) : (
                    <span className={TOKEN_COLORS.plain}>{line}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
