interface BarItem {
  label: string;
  value: number;
}

interface HorizontalBarChartProps {
  data: BarItem[];
  color?: string;
  maxBars?: number;
  onBarClick?: (label: string) => void;
}

export function HorizontalBarChart({
  data,
  color = "#6366f1",
  maxBars = 10,
  onBarClick,
}: HorizontalBarChartProps) {
  const bars = data.slice(0, maxBars);
  const maxValue = Math.max(1, ...bars.map((b) => b.value));

  if (bars.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">
        No data available
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {bars.map((bar) => {
        const pct = (bar.value / maxValue) * 100;
        return (
          <button
            key={bar.label}
            type="button"
            onClick={() => onBarClick?.(bar.label)}
            disabled={!onBarClick}
            className="group flex w-full items-center gap-3 rounded-lg px-1 py-1 text-left transition-colors hover:bg-slate-50 disabled:cursor-default disabled:hover:bg-transparent dark:hover:bg-slate-800/60 dark:disabled:hover:bg-transparent"
          >
            <span className="w-28 shrink-0 truncate text-xs font-medium text-slate-600 dark:text-slate-400">
              {bar.label}
            </span>
            <div className="flex-1">
              <div className="h-5 w-full overflow-hidden rounded-md bg-slate-100 dark:bg-slate-800">
                <div
                  className="h-full rounded-md transition-all duration-500"
                  style={{ width: `${pct}%`, backgroundColor: color }}
                />
              </div>
            </div>
            <span className="w-12 shrink-0 text-right text-xs font-bold tabular-nums text-slate-700 dark:text-slate-300">
              {bar.value.toLocaleString()}
            </span>
          </button>
        );
      })}
    </div>
  );
}
