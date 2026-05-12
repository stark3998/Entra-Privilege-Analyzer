// frontend/src/store/tenantContext.tsx
import { createContext, useContext, useMemo, type ReactNode } from "react";

interface TenantContextValue {
  tenantId: string;
  tenantName: string;
}

const TenantContext = createContext<TenantContextValue | null>(null);

interface TenantProviderProps {
  tenantId: string;
  tenantName: string;
  children: ReactNode;
}

export function TenantProvider({
  tenantId,
  tenantName,
  children,
}: TenantProviderProps) {
  const value = useMemo(
    () => ({ tenantId, tenantName }),
    [tenantId, tenantName],
  );
  return (
    <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
  );
}

/**
 * Access the active tenant context.
 * Throws if used outside a TenantProvider.
 */
export function useTenant(): TenantContextValue {
  const ctx = useContext(TenantContext);
  if (!ctx) {
    throw new Error("useTenant must be used within a TenantProvider");
  }
  return ctx;
}
