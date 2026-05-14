import type { TrendPoint } from "@/api/types";

interface ActivitySparklineProps {
  data: TrendPoint[];
}

const HEIGHT = 80;
const PADDING = { top: 8, right: 8, bottom: 8, left: 8 };

export function ActivitySparkline({ data }: ActivitySparklineProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-20 items-center justify-center text-xs text-slate-400 dark:text-slate-500">
        No activity data
      </div>
    );
  }

  const width = 600;
  const plotW = width - PADDING.left - PADDING.right;
  const plotH = HEIGHT - PADDING.top - PADDING.bottom;

  const values = data.map((p) => p.value);
  const maxVal = Math.max(1, ...values);

  const toX = (i: number) =>
    PADDING.left + (data.length > 1 ? (i / (data.length - 1)) * plotW : plotW / 2);
  const toY = (v: number) => PADDING.top + plotH - (v / maxVal) * plotH;

  const line = data.map((p, i) => `${toX(i)},${toY(p.value)}`).join(" ");
  const area = `${toX(0)},${toY(0)} ${line} ${toX(data.length - 1)},${toY(0)}`;

  return (
    <svg
      viewBox={`0 0 ${width} ${HEIGHT}`}
      className="w-full"
      preserveAspectRatio="xMidYMid meet"
    >
      <polygon points={area} fill="rgba(99,102,241,0.08)" />
      <polyline
        points={line}
        fill="none"
        stroke="#6366f1"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
