import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { Breadcrumbs } from "./Breadcrumbs";
import { CommandPaletteProvider } from "./CommandPalette";

export function AppShell() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);
  const pageKey = segments.slice(0, 4).join("/");

  return (
    <CommandPaletteProvider>
      <div className="flex h-screen flex-col bg-slate-50 dark:bg-slate-950">
        <Header />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-y-auto">
            <div className="border-b border-slate-200/70 bg-white/60 px-8 py-3 backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/40">
              <div className="mx-auto max-w-[88rem]">
                <Breadcrumbs />
              </div>
            </div>
            <div className="px-8 py-7">
              <div className="mx-auto max-w-[88rem]">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={pageKey}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <Outlet />
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </main>
        </div>
      </div>
    </CommandPaletteProvider>
  );
}
