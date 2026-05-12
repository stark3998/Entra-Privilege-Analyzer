// frontend/src/App.tsx
import { Routes, Route, Navigate } from "react-router-dom";
import {
  AuthenticatedTemplate,
  UnauthenticatedTemplate,
} from "@azure/msal-react";
import { AppShell } from "@/components/layout/AppShell";
import { LoginGate } from "@/auth/LoginGate";
import { DashboardPage } from "@/pages/DashboardPage";
import { IdentitiesPage } from "@/pages/IdentitiesPage";
import { IdentityDetailPage } from "@/pages/IdentityDetailPage";
import { RecommendationsPage } from "@/pages/RecommendationsPage";
import { RecommendationDetailPage } from "@/pages/RecommendationDetailPage";
import { useAuth } from "@/auth/useAuth";
import { TenantProvider } from "@/store/tenantContext";
import { getApiClient } from "@/api/client";

const isLocalMode = import.meta.env.VITE_LOCAL_MODE === "true";

function AuthenticatedApp() {
  const { user, acquireToken } = useAuth();

  // Initialize the API client with the token provider
  getApiClient(acquireToken);

  const tenantId = user?.tenantId ?? "unknown";
  const tenantName = user?.name ?? "Unknown Tenant";

  return (
    <TenantProvider tenantId={tenantId} tenantName={tenantName}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/identities" element={<IdentitiesPage />} />
          <Route path="/identities/:id" element={<IdentityDetailPage />} />
          <Route path="/recommendations" element={<RecommendationsPage />} />
          <Route path="/recommendations/:id" element={<RecommendationDetailPage />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </TenantProvider>
  );
}

function LocalModeBanner() {
  return (
    <div className="bg-amber-500 px-4 py-1 text-center text-xs font-medium text-amber-950">
      LOCAL MODE -- Authentication is disabled
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
