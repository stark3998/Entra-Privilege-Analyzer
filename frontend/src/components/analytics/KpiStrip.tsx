interface KpiItem {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}

interface KpiStripProps {
  items: KpiItem[];
}

export function KpiStrip({ items }: KpiStripProps) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {items.map((item) => (
        <div key={item.label} className="card px-5 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
            {item.label}
          </p>
          <p
            className="mt-1 text-2xl font-bold tabular-nums"
            style={{ color: item.color }}
          >
            <span className="text-slate-900 dark:text-white">{item.value}</span>
          </p>
          {item.sub && (
            <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
              {item.sub}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
