import type { ReactNode } from "react";
import { ApiError } from "@/api/client";
import { EmptyState } from "@/components/common/EmptyState";

function ShieldIcon() {
  return (
    <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 3l7.5 3v5.25c0 4.142-2.822 7.88-7.5 9.75-4.678-1.87-7.5-5.608-7.5-9.75V6L12 3z"
      />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 12.75l1.5 1.5 3-3.75" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m0 3.75h.008v.008H12v-.008zm8.25-.75A8.25 8.25 0 103.75 12a8.25 8.25 0 0016.5 0z"
      />
    </svg>
  );
}

export function AccessDeniedState({
  title = "Access denied",
  description = "Your current app role does not allow access to this governance view.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <EmptyState
      title={title}
      description={description}
      icon={<ShieldIcon />}
    />
  );
}

export function GovernanceErrorState({
  error,
  feature,
  action,
}: {
  error: unknown;
  feature: string;
  action?: ReactNode;
}) {
  let title = `Failed to load ${feature}`;
  let description =
    "The governance service returned an unexpected response. Please retry after the backend deployment completes.";

  if (error instanceof ApiError) {
    if (error.status === 403) {
      title = "Access denied";
      description = `You do not currently have permission to view ${feature}.`;
    } else if (error.status === 404) {
      title = `${feature} was not found`;
      description =
        error.body || "The requested governance resource or configuration was not found.";
    } else if ([405, 501, 503].includes(error.status)) {
      title = `${feature} is not available yet`;
      description =
        "This frontend is ready, but the backend endpoint is not currently available. Deploy or finish the governance API and refresh the page.";
    } else if (error.body) {
      description = error.body;
    }
  } else if (error instanceof Error && error.message) {
    description = error.message;
  }

  return (
    <EmptyState
      title={title}
      description={description}
      action={action}
      icon={<ErrorIcon />}
    />
  );
}
