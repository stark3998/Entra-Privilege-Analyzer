// frontend/src/components/dashboard/TrendChart.tsx
import { useState, useCallback, useRef, useMemo } from "react";
import clsx from "clsx";
import type { TrendPoint } from "@/api/types";

type TrendTab = "risk" | "drift" | "actions";

interface TrendChartProps {
  /** Risk score trend points (date + value). */
  riskTrend: TrendPoint[];
  /** Drift alerts trend points. */
  driftTrend: TrendPoint[];
  /** Actions trend points. */
  actionsTrend: TrendPoint[];
}

const TAB_CONFIG: { key: TrendTab; label: string; color: string; fillColor: string }[] = [
  { key: "risk", label: "Risk Score", color: "#ef4444", fillColor: "rgba(239,68,68,0.1)" },
  { key: "drift", label: "Drift Alerts", color: "#f59e0b", fillColor: "rgba(245,158,11,0.1)" },
  { key: "actions", label: "Actions", color: "#3b82f6", fillColor: "rgba(59,130,246,0.1)" },
];

const CHART_HEIGHT = 200;
const PADDING = { top: 20, right: 16, bottom: 32, left: 48 };

interface TooltipInfo {
  x: number;
  y: number;
  date: string;
  value: number;
}

/**
 * SVG line chart with filled area underneath.
 * Three toggle tabs for Risk Score, Drift Alerts, and Actions.
 * Tooltip on hover. Responsive width, fixed 200px height.
 *
 * Usage:
 * ```tsx
 * <TrendChart riskTrend={data.risk_score_trend} driftTrend={data.drift_alerts_trend} actionsTrend={data.actions_trend} />
 * ```
 */
export function TrendChart({ riskTrend, driftTrend, actionsTrend }: TrendChartProps) {
  const [activeTab, setActiveTab] = useState<TrendTab>("risk");
  const [tooltip, setTooltip] = useState<TooltipInfo | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const dataMap: Record<TrendTab, TrendPoint[]> = useMemo(
    () => ({ risk: riskTrend, drift: driftTrend, actions: actionsTrend }),
    [riskTrend, driftTrend, actionsTrend],
  );

  const points = dataMap[activeTab];
  const tabConfig = TAB_CONFIG.find((t) => t.key === activeTab)!;

  // Compute chart dimensions and scales
  const chartWidth = 600; // Will be responsive via viewBox
  const plotWidth = chartWidth - PADDING.left - PADDING.right;
  const plotHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom;

  const values = points.map((p) => p.value);
  const minVal = Math.min(0, ...values);
  const maxVal = Math.max(1, ...values);
  const yRange = maxVal - minVal || 1;

  const toX = useCallback(
    (i: number) => PADDING.left + (points.length > 1 ? (i / (points.length - 1)) * plotWidth : plotWidth / 2),
    [points.length, plotWidth],
  );
  const toY = useCallback(
    (v: number) => PADDING.top + plotHeight - ((v - minVal) / yRange) * plotHeight,
    [minVal, yRange, plotHeight],
  );

  // Build polyline points string
  const linePoints = points.map((p, i) => `${toX(i)},${toY(p.value)}`).join(" ");

  // Build area polygon (closed path to bottom)
  const areaPoints =
    points.length > 0
      ? `${toX(0)},${toY(minVal)} ${linePoints} ${toX(points.length - 1)},${toY(minVal)}`
      : "";

  // Y-axis ticks (5 ticks)
  const yTicks = Array.from({ length: 5 }, (_, i) =>
    Math.round(minVal + (yRange * i) / 4),
  );

  // X-axis labels (show ~6 evenly spaced dates)
  const xLabelCount = Math.min(6, points.length);
  const xLabels = Array.from({ length: xLabelCount }, (_, i) => {
    const idx = points.length > 1 ? Math.round((i / (xLabelCount - 1)) * (points.length - 1)) : 0;
    return { idx, label: formatDateShort(points[idx]?.date ?? "") };
  });

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!svgRef.current || points.length === 0) return;
      const rect = svgRef.current.getBoundingClientRect();
      const svgX = ((e.clientX - rect.left) / rect.width) * chartWidth;
      const relX = svgX - PADDING.left;
      const idx = Math.round((relX / plotWidth) * (points.length - 1));
      const clampedIdx = Math.max(0, Math.min(points.length - 1, idx));
      const pt = points[clampedIdx];
      if (pt) {
        setTooltip({
          x: toX(clampedIdx),
          y: toY(pt.value),
          date: pt.date,
          value: pt.value,
        });
      }
    },
    [points, toX, toY, plotWidth, chartWidth],
  );

  const handleMouseLeave = useCallback(() => setTooltip(null), []);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      {/* Tabs */}
      <div className="mb-4 flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
        {TAB_CONFIG.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={clsx(
              "flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              activeTab === tab.key
                ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
                : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Chart */}
      {points.length === 0 ? (
        <div className="flex h-[200px] items-center justify-center text-sm text-slate-400 dark:text-slate-500">
          No trend data available
        </div>
      ) : (
        <svg
          ref={svgRef}
          viewBox={`0 0 ${chartWidth} ${CHART_HEIGHT}`}
          className="w-full"
          preserveAspectRatio="xMidYMid meet"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* Grid lines */}
          {yTicks.map((tick) => (
            <line
              key={tick}
              x1={PADDING.left}
              y1={toY(tick)}
              x2={chartWidth - PADDING.right}
              y2={toY(tick)}
              stroke="currentColor"
              strokeWidth={0.5}
              className="text-slate-200 dark:text-slate-700"
            />
          ))}

          {/* Y-axis labels */}
          {yTicks.map((tick) => (
            <text
              key={`yl-${tick}`}
              x={PADDING.left - 8}
              y={toY(tick) + 4}
              textAnchor="end"
              className="fill-slate-400 text-[10px] dark:fill-slate-500"
            >
              {tick}
            </text>
          ))}

          {/* X-axis labels */}
          {xLabels.map(({ idx, label }) => (
            <text
              key={`xl-${idx}`}
              x={toX(idx)}
              y={CHART_HEIGHT - 4}
              textAnchor="middle"
              className="fill-slate-400 text-[10px] dark:fill-slate-500"
            >
              {label}
            </text>
          ))}

          {/* Filled area */}
          <polygon
            points={areaPoints}
            fill={tabConfig.fillColor}
          />

          {/* Line */}
          <polyline
            points={linePoints}
            fill="none"
            stroke={tabConfig.color}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {/* Tooltip indicator */}
          {tooltip && (
            <>
              <circle cx={tooltip.x} cy={tooltip.y} r={4} fill={tabConfig.color} />
              <line
                x1={tooltip.x}
                y1={PADDING.top}
                x2={tooltip.x}
                y2={CHART_HEIGHT - PADDING.bottom}
                stroke={tabConfig.color}
                strokeWidth={0.5}
                strokeDasharray="4 2"
              />
            </>
          )}
        </svg>
      )}

      {/* Tooltip text */}
      {tooltip && (
        <div className="mt-2 flex items-center justify-center gap-3 text-xs text-slate-500 dark:text-slate-400">
          <span>{formatDateLong(tooltip.date)}</span>
          <span className="font-semibold text-slate-900 dark:text-white">
            {tooltip.value}
          </span>
        </div>
      )}
    </div>
  );
}

function formatDateShort(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function formatDateLong(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
