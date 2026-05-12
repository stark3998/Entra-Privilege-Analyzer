// frontend/src/pages/DashboardPage.tsx

interface SummaryCard {
  title: string;
  value: string;
  color: string;
  iconPath: string;
}

const CARDS: SummaryCard[] = [
  {
    title: "Total Identities",
    value: "—",
    color: "text-brand-600 dark:text-brand-400",
    iconPath:
      "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z",
  },
  {
    title: "Over-Privileged",
    value: "—",
    color: "text-risk-high dark:text-risk-high-light",
    iconPath:
      "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z",
  },
  {
    title: "Drift Alerts",
    value: "—",
    color: "text-drift dark:text-drift-light",
    iconPath: "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6",
  },
  {
    title: "Best Practice Violations",
    value: "—",
    color: "text-risk-medium dark:text-risk-medium-light",
    iconPath: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  },
];

export function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Overview of your Entra ID permissions posture
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {CARDS.map((card) => (
          <div
            key={card.title}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
          >
            <div className="flex items-center gap-3">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 ${card.color}`}
              >
                <svg
                  className="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d={card.iconPath}
                  />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                  {card.title}
                </p>
                <p className="text-2xl font-bold text-slate-900 dark:text-white">
                  {card.value}
                </p>
              </div>
            </div>
            <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
              Coming soon
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
