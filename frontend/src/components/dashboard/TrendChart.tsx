import { useState, useCallback, useRef, useMemo } from "react";
import clsx from "clsx";
import { Tooltip } from "@/components/common/Tooltip";
import type { TrendPoint } from "@/api/types";

type TrendTab = "risk" | "drift" | "actions";

interface TrendChartProps {
  riskTrend: TrendPoint[];
  driftTrend: TrendPoint[];
  actionsTrend: TrendPoint[];
}

const TAB_CONFIG: { key: TrendTab; label: string; color: string; fillColor: string; hint: string }[] = [
  { key: "risk", label: "Risk Score", color: "#ef4444", fillColor: "rgba(239,68,68,0.08)", hint: "Average risk score over time" },
  { key: "drift", label: "Drift Alerts", color: "#f59e0b", fillColor: "rgba(245,158,11,0.08)", hint: "New drift alerts per day" },
  { key: "actions", label: "Actions", color: "#6366f1", fillColor: "rgba(99,102,241,0.08)", hint: "Permission actions observed daily" },
];

const CHART_HEIGHT = 200;
const PADDING = { top: 20, right: 16, bottom: 32, left: 48 };

interface TooltipInfo {
  x: number;
  y: number;
  date: string;
  value: number;
}

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

  const chartWidth = 600;
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

  const linePoints = points.map((p, i) => `${toX(i)},${toY(p.value)}`).join(" ");
  const areaPoints =
    points.length > 0
      ? `${toX(0)},${toY(minVal)} ${linePoints} ${toX(points.length - 1)},${toY(minVal)}`
      : "";

  const yTicks = Array.from({ length: 5 }, (_, i) => Math.round(minVal + (yRange * i) / 4));

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
        setTooltip({ x: toX(clampedIdx), y: toY(pt.value), date: pt.date, value: pt.value });
      }
    },
    [points, toX, toY, plotWidth, chartWidth],
  );

  const handleMouseLeave = useCallback(() => setTooltip(null), []);

  return (
    <div className="card p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">30-Day Trends</h3>
          <Tooltip content="Historical trend data for the last 30 days">
            <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </Tooltip>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
          {TAB_CONFIG.map((tab) => (
            <Tooltip key={tab.key} content={tab.hint} position="bottom">
              <button
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={clsx(
                  "rounded-lg px-3 py-1.5 text-xs font-semibold transition-all",
                  activeTab === tab.key
                    ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
                    : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200",
                )}
              >
                {tab.label}
              </button>
            </Tooltip>
          ))}
        </div>
      </div>

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
          {yTicks.map((tick) => (
            <line
              key={tick}
              x1={PADDING.left} y1={toY(tick)}
              x2={chartWidth - PADDING.right} y2={toY(tick)}
              stroke="currentColor" strokeWidth={0.5}
              className="text-slate-100 dark:text-slate-800"
            />
          ))}

          {yTicks.map((tick) => (
            <text
              key={`yl-${tick}`}
              x={PADDING.left - 8} y={toY(tick) + 4}
              textAnchor="end"
              className="fill-slate-400 text-[10px] dark:fill-slate-500"
            >
              {tick}
            </text>
          ))}

          {xLabels.map(({ idx, label }) => (
            <text
              key={`xl-${idx}`}
              x={toX(idx)} y={CHART_HEIGHT - 4}
              textAnchor="middle"
              className="fill-slate-400 text-[10px] dark:fill-slate-500"
            >
              {label}
            </text>
          ))}

          <polygon points={areaPoints} fill={tabConfig.fillColor} />

          <polyline
            points={linePoints}
            fill="none" stroke={tabConfig.color} strokeWidth={2}
            strokeLinejoin="round" strokeLinecap="round"
          />

          {tooltip && (
            <>
              <circle cx={tooltip.x} cy={tooltip.y} r={5} fill="white" stroke={tabConfig.color} strokeWidth={2} />
              <line
                x1={tooltip.x} y1={PADDING.top}
                x2={tooltip.x} y2={CHART_HEIGHT - PADDING.bottom}
                stroke={tabConfig.color} strokeWidth={0.5} strokeDasharray="4 2"
              />
            </>
          )}
        </svg>
      )}

      {tooltip && (
        <div className="mt-2 flex items-center justify-center gap-3 text-xs text-slate-500 dark:text-slate-400">
          <span>{formatDateLong(tooltip.date)}</span>
          <span className="rounded-md bg-slate-100 px-2 py-0.5 font-bold text-slate-900 dark:bg-slate-800 dark:text-white">
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
