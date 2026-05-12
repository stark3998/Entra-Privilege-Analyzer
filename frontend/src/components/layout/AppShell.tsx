// frontend/src/components/layout/AppShell.tsx
import { Outlet } from "react-router-dom";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export function AppShell() {
  return (
    <div className="flex h-screen flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-white p-6 dark:bg-slate-950">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
