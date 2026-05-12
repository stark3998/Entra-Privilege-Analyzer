// frontend/src/pages/IdentityDetailPage.tsx
import { useParams, useNavigate } from "react-router-dom";
import { useIdentityDetail } from "@/api/hooks";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import { IdentityDetail } from "@/components/identities/IdentityDetail";
import { ApiError } from "@/api/client";

export function IdentityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useIdentityDetail(id ?? "");

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={() => navigate("/identities")}
        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm font-medium text-slate-600 transition-colors hover:bg-brand-50 hover:text-brand-700 dark:text-slate-400 dark:hover:bg-brand-900/20 dark:hover:text-brand-300"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Back to Identities
      </button>

      {/* Loading */}
      {isLoading && <LoadingSpinner message="Loading identity..." />}

      {/* Error / 404 */}
      {isError && (
        <EmptyState
          title={
            error instanceof ApiError && error.status === 404
              ? "Identity not found"
              : "Failed to load identity"
          }
          description={
            error instanceof ApiError && error.status === 404
              ? "The identity you are looking for does not exist or has been removed."
              : error instanceof Error
                ? error.message
                : "An unexpected error occurred."
          }
          icon={
            <svg
              className="h-10 w-10"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          }
          action={
            <button
              type="button"
              onClick={() => navigate("/identities")}
              className="btn-primary"
            >
              Return to Identities
            </button>
          }
        />
      )}

      {/* Detail view */}
      {data && <IdentityDetail identity={data} />}
    </div>
  );
}
