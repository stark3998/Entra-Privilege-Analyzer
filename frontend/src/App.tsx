// frontend/src/App.tsx
import { Routes, Route, Navigate } from "react-router-dom";
import {
  AuthenticatedTemplate,
  UnauthenticatedTemplate,
} from "@azure/msal-react";
import { AppShell } from "@/components/layout/AppShell";
import { LoginGate } from "@/auth/LoginGate";
import { DashboardPage } from "@/pages/DashboardPage";
import { AnalyticsPage } from "@/pages/AnalyticsPage";
import { IdentitiesPage } from "@/pages/IdentitiesPage";
import { IdentityDetailPage } from "@/pages/IdentityDetailPage";
import { RecommendationsPage } from "@/pages/RecommendationsPage";
import { RecommendationDetailPage } from "@/pages/RecommendationDetailPage";
import { DriftPage } from "@/pages/DriftPage";
import { DriftDetailPage } from "@/pages/DriftDetailPage";
import { BestPracticesPage } from "@/pages/BestPracticesPage";
import { BestPracticeDetailPage } from "@/pages/BestPracticeDetailPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { ProjectsHomePage } from "@/pages/ProjectsHomePage";
import { ProjectCreatePage } from "@/pages/ProjectCreatePage";
import { ScanPage } from "@/pages/ScanPage";
import { ProjectMembersPage } from "@/pages/ProjectMembersPage";
import { useAuth } from "@/auth/useAuth";
import { ProjectProvider } from "@/store/projectContext";
import { getApiClient } from "@/api/client";

const isLocalMode = import.meta.env.VITE_LOCAL_MODE === "true";

function AuthenticatedApp() {
  const { acquireToken } = useAuth();

  // Initialize the API client with the token provider
  getApiClient(acquireToken);

  return (
    <Routes>
      {/* Project list & creation — no AppShell */}
      <Route path="/projects" element={<ProjectsHomePage />} />
      <Route path="/projects/new" element={<ProjectCreatePage />} />

      {/* Project-scoped pages — wrapped by ProjectProvider + AppShell */}
      <Route
        path="/projects/:projectId/*"
        element={
          <ProjectProvider>
            <AppShell />
          </ProjectProvider>
        }
      >
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="identities" element={<IdentitiesPage />} />
        <Route path="identities/:id" element={<IdentityDetailPage />} />
        <Route path="recommendations" element={<RecommendationsPage />} />
        <Route path="recommendations/:id" element={<RecommendationDetailPage />} />
        <Route path="drift" element={<DriftPage />} />
        <Route path="drift/:id" element={<DriftDetailPage />} />
        <Route path="best-practices" element={<BestPracticesPage />} />
        <Route path="best-practices/:id" element={<BestPracticeDetailPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="scan" element={<ScanPage />} />
        <Route path="members" element={<ProjectMembersPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="*" element={<Navigate to="dashboard" replace />} />
      </Route>

      {/* Root redirect */}
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}

function LocalModeBanner() {
  return (
    <div className="border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-center text-xs font-semibold text-amber-700 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-400">
      LOCAL MODE &mdash; Authentication is disabled
    </div>
  );
}

export function App() {
  if (isLocalMode) {
    return (
      <>
        <LocalModeBanner />
        <AuthenticatedApp />
      </>
    );
  }

  return (
    <>
      <UnauthenticatedTemplate>
        <LoginGate />
      </UnauthenticatedTemplate>
      <AuthenticatedTemplate>
        <AuthenticatedApp />
      </AuthenticatedTemplate>
    </>
  );
}
