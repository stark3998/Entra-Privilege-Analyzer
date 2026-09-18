import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useProjectContext } from "@/store/projectContext";
import { useAuth } from "@/auth/useAuth";
import {
  useIdentities,
  useRecommendations,
  useDriftAlerts,
  useViolations,
} from "@/api/hooks";
import { visiblePages, type PageEntry } from "./pageRegistry";

interface CommandPaletteContextValue {
  open: () => void;
  close: () => void;
  toggle: () => void;
  isOpen: boolean;
}

const Ctx = createContext<CommandPaletteContextValue | null>(null);

export function useCommandPalette(): CommandPaletteContextValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCommandPalette must be used within CommandPaletteProvider");
  return ctx;
}

export function CommandPaletteProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((v) => !v), []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        toggle();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  const value = useMemo(() => ({ open, close, toggle, isOpen }), [open, close, toggle, isOpen]);

  return (
    <Ctx.Provider value={value}>
      {children}
      <AnimatePresence>
        {isOpen && <CommandDialog onClose={close} />}
      </AnimatePresence>
    </Ctx.Provider>
  );
}

interface Result {
  id: string;
  title: string;
  subtitle: string;
  group: string;
  to: string;
  badge?: string;
}

function CommandDialog({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const navigate = useNavigate();
  const { projectId } = useProjectContext();
  const { roles } = useAuth();
  const base = `/projects/${projectId}`;
  const q = query.trim().toLowerCase();

  // Entity searches (only meaningful once there's a query).
  const enabled = q.length > 0;
  const { data: identities } = useIdentities({ search: enabled ? query : undefined, size: 6 });
  const { data: recs } = useRecommendations({ search: enabled ? query : undefined, size: 6 });
  const { data: drifts } = useDriftAlerts({ search: enabled ? query : undefined, size: 6 });
  const { data: viols } = useViolations({ size: 50 });

  const pages: PageEntry[] = useMemo(() => visiblePages(roles), [roles]);

  const results: Result[] = useMemo(() => {
    const out: Result[] = [];

    // Pages
    const pageMatches = pages.filter((p) => {
      if (!q) return true;
      return (
        p.label.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.keywords.some((k) => k.includes(q))
      );
    });
    for (const p of pageMatches.slice(0, q ? 5 : pages.length)) {
      out.push({
        id: `page-${p.suffix}`,
        title: p.label,
        subtitle: p.description,
        group: `Go to · ${p.group}`,
        to: `${base}/${p.suffix}`,
      });
    }

    if (enabled) {
      for (const i of identities?.items ?? []) {
        out.push({
          id: `id-${i.id}`,
          title: i.display_name,
          subtitle: i.upn ?? i.identity_type,
          group: "Identities",
          to: `${base}/identities/${i.id}`,
          badge: i.identity_type,
        });
      }
      for (const r of recs?.items ?? []) {
        out.push({
          id: `rec-${r.id}`,
          title: r.identity_display_name,
          subtitle: `Recommendation · ${r.reduction_score.toFixed(0)}% reduction`,
          group: "Recommendations",
          to: `${base}/recommendations/${r.identity_id}`,
        });
      }
      for (const d of drifts?.items ?? []) {
        out.push({
          id: `drift-${d.id}`,
          title: d.identity_display_name,
          subtitle: `${d.drift_type.replace("_", " ")} · ${d.action}`,
          group: "Drift Alerts",
          to: `${base}/drift/${d.id}`,
          badge: d.severity,
        });
      }
      for (const v of (viols?.items ?? []).filter(
        (v) =>
          v.identity_display_name.toLowerCase().includes(q) ||
          v.title.toLowerCase().includes(q),
      ).slice(0, 6)) {
        out.push({
          id: `viol-${v.id}`,
          title: v.title,
          subtitle: v.identity_display_name,
          group: "Best Practices",
          to: `${base}/best-practices/${v.id}`,
          badge: v.priority,
        });
      }
    }

    return out;
  }, [pages, q, enabled, identities, recs, drifts, viols, base]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  const go = useCallback(
    (r: Result | undefined) => {
      if (!r) return;
      navigate(r.to);
      onClose();
    },
    [navigate, onClose],
  );

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(results[active]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  // Group results in order of appearance.
  const grouped = useMemo(() => {
    const map = new Map<string, Result[]>();
    results.forEach((r) => {
      const arr = map.get(r.group) ?? [];
      arr.push(r);
      map.set(r.group, arr);
    });
    return Array.from(map.entries());
  }, [results]);

  let flatIndex = -1;

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
    >
      <div
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-overlay dark:border-slate-700 dark:bg-slate-900"
        initial={{ opacity: 0, y: -12, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -8, scale: 0.98 }}
        transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="flex items-center gap-3 border-b border-slate-100 px-4 dark:border-slate-800">
          <svg className="h-5 w-5 shrink-0 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search pages, identities, recommendations, alerts…"
            className="w-full bg-transparent py-4 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-white"
          />
          <kbd className="hidden rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-400 dark:border-slate-700 dark:bg-slate-800 sm:block">
            ESC
          </kbd>
        </div>

        <div className="max-h-[52vh] overflow-y-auto p-2">
          {grouped.length === 0 ? (
            <div className="px-3 py-10 text-center text-sm text-slate-400">
              No results for “{query}”
            </div>
          ) : (
            grouped.map(([group, items]) => (
              <div key={group} className="mb-1">
                <p className="px-3 pb-1 pt-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  {group}
                </p>
                {items.map((r) => {
                  flatIndex += 1;
                  const idx = flatIndex;
                  const isActive = idx === active;
                  return (
                    <button
                      key={r.id}
                      onMouseEnter={() => setActive(idx)}
                      onClick={() => go(r)}
                      className={`flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition-colors ${
                        isActive
                          ? "bg-brand-50 dark:bg-brand-950/40"
                          : "hover:bg-slate-50 dark:hover:bg-slate-800/60"
                      }`}
                    >
                      <span className="min-w-0">
                        <span className={`block truncate text-sm font-medium ${isActive ? "text-brand-700 dark:text-brand-300" : "text-slate-700 dark:text-slate-200"}`}>
                          {r.title}
                        </span>
                        <span className="block truncate text-xs text-slate-400 dark:text-slate-500">
                          {r.subtitle}
                        </span>
                      </span>
                      {r.badge && (
                        <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold capitalize text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                          {r.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2 text-[11px] text-slate-400 dark:border-slate-800 dark:text-slate-500">
          <span className="flex items-center gap-2">
            <kbd className="rounded border border-slate-200 px-1 dark:border-slate-700">↑</kbd>
            <kbd className="rounded border border-slate-200 px-1 dark:border-slate-700">↓</kbd>
            to navigate
          </span>
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-slate-200 px-1 dark:border-slate-700">↵</kbd>
            to open
          </span>
        </div>
      </motion.div>
    </motion.div>
  );
}
