// frontend/src/auth/useAuth.ts
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { useCallback, useMemo } from "react";
import { apiScopes } from "./msal";

interface AuthUser {
  name: string;
  email: string;
  tenantId: string;
  oid: string;
}

interface AuthResult {
  isAuthenticated: boolean;
  user: AuthUser | null;
  roles: string[];
  acquireToken: () => Promise<string>;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}

const isLocalMode = import.meta.env.VITE_LOCAL_MODE === "true";

const LOCAL_USER: AuthUser = {
  name: "Local Developer",
  email: "dev@localhost",
  tenantId: "local-dev-tenant",
  oid: "local-dev-user",
};

/**
 * Custom hook for authentication state and operations.
 * In local mode, returns mock values without touching MSAL.
 */
export function useAuth(): AuthResult {
  if (isLocalMode) {
    return {
      isAuthenticated: true,
      user: LOCAL_USER,
      roles: ["SecurityEngineer", "IAMAdmin", "Executive"],
      acquireToken: () => Promise.resolve("local-dev-token"),
      signIn: () => Promise.resolve(),
      signOut: () => Promise.resolve(),
    };
  }

  return useAuthMsal();
}

function useAuthMsal(): AuthResult {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  const account = accounts[0] ?? null;

  const user = useMemo((): AuthUser | null => {
    if (!account) return null;
    const claims = account.idTokenClaims as
      | Record<string, unknown>
      | undefined;
    return {
      name: account.name ?? "",
      email: account.username ?? "",
      tenantId: (claims?.tid as string) ?? "",
      oid: (claims?.oid as string) ?? "",
    };
  }, [account]);

  const roles = useMemo((): string[] => {
    if (!account) return [];
    const claims = account.idTokenClaims as
      | Record<string, unknown>
      | undefined;
    const raw = claims?.roles;
    return Array.isArray(raw) ? (raw as string[]) : [];
  }, [account]);

  const acquireToken = useCallback(async (): Promise<string> => {
    if (!account) throw new Error("No active account");
    const response = await instance.acquireTokenSilent({
      scopes: apiScopes,
      account,
    });
    return response.accessToken;
  }, [instance, account]);

  const signIn = useCallback(async (): Promise<void> => {
    await instance.loginRedirect({ scopes: apiScopes });
  }, [instance]);

  const signOut = useCallback(async (): Promise<void> => {
    await instance.logoutRedirect();
  }, [instance]);

  return { isAuthenticated, user, roles, acquireToken, signIn, signOut };
}
