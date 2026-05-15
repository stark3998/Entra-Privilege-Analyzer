import { useState } from "react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { useCreateProject, useValidatePermissions } from "@/api/projectHooks";
import type { Project, PermissionValidationResult } from "@/api/types";

const REQUIRED_PERMISSIONS = [
  "AuditLog.Read.All",
  "Directory.Read.All",
  "User.Read.All",
  "Application.Read.All",
  "RoleManagement.Read.Directory",
];

type Step = 1 | 2 | 3 | 4;

const STEP_LABELS = ["Details", "Credentials", "Validate", "Done"];

function StepIndicator({ current }: { current: Step }) {
  return (
    <div className="flex items-center gap-2">
      {STEP_LABELS.map((label, i) => {
        const step = (i + 1) as Step;
        const isActive = step === current;
        const isDone = step < current;
        return (
          <div key={label} className="flex items-center gap-2">
            {i > 0 && (
              <div
                className={clsx(
                  "h-px w-8",
                  isDone
                    ? "bg-brand-500"
                    : "bg-slate-200 dark:bg-slate-700",
                )}
              />
            )}
            <div className="flex items-center gap-2">
              <div
                className={clsx(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold",
                  isActive
                    ? "bg-brand-600 text-white"
                    : isDone
                      ? "bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300"
                      : "bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500",
                )}
              >
                {isDone ? (
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  step
                )}
              </div>
              <span
                className={clsx(
                  "text-xs font-medium",
                  isActive
                    ? "text-slate-900 dark:text-white"
                    : "text-slate-400 dark:text-slate-500",
                )}
              >
                {label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ProjectCreatePage() {
  const navigate = useNavigate();
  const createProject = useCreateProject();
  const [createdProject, setCreatedProject] = useState<Project | null>(null);
  const validatePermissions = useValidatePermissions(createdProject?.id ?? "");

  const [step, setStep] = useState<Step>(1);
  const [name, setName] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [validationResult, setValidationResult] =
    useState<PermissionValidationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canProceedStep1 =
    name.trim() && tenantId.trim() && tenantName.trim();
  const canProceedStep2 = clientId.trim() && clientSecret.trim();

  function handleCreateAndValidate() {
    setError(null);
    createProject.mutate(
      {
        name: name.trim(),
        target_tenant_id: tenantId.trim(),
        target_tenant_name: tenantName.trim(),
        client_id: clientId.trim(),
        client_secret: clientSecret.trim(),
      },
      {
        onSuccess: (project) => {
          setCreatedProject(project);
          setValidationResult(project.permission_status);
          setStep(3);
        },
        onError: (err) => {
          setError(
            err instanceof Error ? err.message : "Failed to create project.",
          );
        },
      },
    );
  }

  function handleRevalidate() {
    if (!createdProject) return;
    setError(null);
    validatePermissions.mutate(undefined, {
      onSuccess: (result) => {
        setValidationResult(result);
      },
      onError: (err) => {
        setError(
          err instanceof Error ? err.message : "Validation failed.",
        );
      },
    });
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-8">
      <div>
        <button
          onClick={() => navigate("/projects")}
          className="mb-4 flex items-center gap-1.5 text-sm font-medium text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Projects
        </button>
        <h1 className="page-title">New Project</h1>
        <p className="page-subtitle">
          Connect to an Entra ID tenant for permissions analysis
        </p>
      </div>

      <StepIndicator current={step} />

      {error && (
        <div className="card border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Step 1: Basic Info */}
      {step === 1 && (
        <div className="card space-y-5 p-6">
          <div>
            <label
              htmlFor="project-name"
              className="block text-sm font-semibold text-slate-700 dark:text-slate-300"
            >
              Project Name
            </label>
            <input
              id="project-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Production Tenant"
              className="input-base mt-1.5 block w-full"
            />
          </div>
          <div>
            <label
              htmlFor="tenant-id"
              className="block text-sm font-semibold text-slate-700 dark:text-slate-300"
            >
              Target Tenant ID
            </label>
            <input
              id="tenant-id"
              type="text"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="input-base mt-1.5 block w-full font-mono text-sm"
            />
            <p className="mt-1.5 text-xs text-slate-400 dark:text-slate-500">
              The Azure AD / Entra ID tenant ID to scan
            </p>
          </div>
          <div>
            <label
              htmlFor="tenant-name"
              className="block text-sm font-semibold text-slate-700 dark:text-slate-300"
            >
              Tenant Display Name
            </label>
            <input
              id="tenant-name"
              type="text"
              value={tenantName}
              onChange={(e) => setTenantName(e.target.value)}
              placeholder="e.g. Contoso Ltd"
              className="input-base mt-1.5 block w-full"
            />
          </div>
          <div className="flex justify-end pt-2">
            <button
              onClick={() => setStep(2)}
              disabled={!canProceedStep1}
              className="btn-primary"
            >
              Next: Credentials
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Credentials */}
      {step === 2 && (
        <div className="card space-y-5 p-6">
          <div className="rounded-xl bg-blue-50 p-4 text-sm text-blue-700 dark:bg-blue-900/20 dark:text-blue-300">
            <p className="font-semibold">App Registration Required</p>
            <p className="mt-1 text-xs">
              Create an app registration in the target tenant with the following
              application permissions: AuditLog.Read.All, Directory.Read.All,
              User.Read.All, Application.Read.All, RoleManagement.Read.Directory
            </p>
          </div>
          <div>
            <label
              htmlFor="client-id"
              className="block text-sm font-semibold text-slate-700 dark:text-slate-300"
            >
              Client ID (Application ID)
            </label>
            <input
              id="client-id"
              type="text"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="input-base mt-1.5 block w-full font-mono text-sm"
            />
          </div>
          <div>
            <label
              htmlFor="client-secret"
              className="block text-sm font-semibold text-slate-700 dark:text-slate-300"
            >
              Client Secret
            </label>
            <input
              id="client-secret"
              type="password"
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              placeholder="Enter client secret value"
              className="input-base mt-1.5 block w-full"
            />
            <p className="mt-1.5 text-xs text-slate-400 dark:text-slate-500">
              Encrypted at rest using AES-256-GCM. Never stored in plaintext.
            </p>
          </div>
          <div className="flex justify-between pt-2">
            <button onClick={() => setStep(1)} className="btn-secondary">
              Back
            </button>
            <button
              onClick={handleCreateAndValidate}
              disabled={!canProceedStep2 || createProject.isPending}
              className="btn-primary"
            >
              {createProject.isPending ? (
                <>
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Creating...
                </>
              ) : (
                "Create & Validate"
              )}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Validation Results */}
      {step === 3 && (
        <div className="card space-y-5 p-6">
          <h2 className="section-title">Permission Validation</h2>
          <div className="space-y-2">
            {REQUIRED_PERMISSIONS.map((perm) => {
              const granted = validationResult?.granted?.includes(perm);
              return (
                <div
                  key={perm}
                  className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50/50 px-4 py-3 dark:border-slate-800 dark:bg-slate-800/30"
                >
                  {granted ? (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/30">
                      <svg className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  ) : (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
                      <svg className="h-3.5 w-3.5 text-red-600 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </div>
                  )}
                  <span className="text-sm font-mono text-slate-700 dark:text-slate-300">
                    {perm}
                  </span>
                </div>
              );
            })}
          </div>

          {validationResult?.valid ? (
            <div className="rounded-xl bg-emerald-50 p-4 text-sm font-medium text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400">
              All required permissions are granted. Your project is ready to
              scan.
            </div>
          ) : (
            <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
              <p className="font-medium">Some permissions are missing.</p>
              <p className="mt-1 text-xs">
                Grant the missing permissions in the Azure portal, then
                re-validate.
              </p>
            </div>
          )}

          <div className="flex justify-between pt-2">
            <button onClick={handleRevalidate} className="btn-secondary">
              Re-validate
            </button>
            <button onClick={() => setStep(4)} className="btn-primary">
              {validationResult?.valid ? "Finish Setup" : "Continue Anyway"}
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Success */}
      {step === 4 && createdProject && (
        <div className="card p-8 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 dark:bg-emerald-900/20">
            <svg className="h-7 w-7 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="mt-4 text-lg font-semibold text-slate-900 dark:text-white">
            Project Created
          </h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            <span className="font-medium text-slate-700 dark:text-slate-300">
              {createdProject.name}
            </span>{" "}
            is ready. Run your first scan to start analyzing permissions.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <button
              onClick={() => navigate("/projects")}
              className="btn-secondary"
            >
              Back to Projects
            </button>
            <button
              onClick={() =>
                navigate(`/projects/${createdProject.id}/scan`)
              }
              className="btn-primary"
            >
              Run First Scan
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
