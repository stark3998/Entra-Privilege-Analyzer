import clsx from "clsx";
import type {
  EvidenceCoverageStatus,
  GovernanceConnectorHealth,
  GovernanceConnectorSyncMode,
  GovernanceWorkflowStatus,
  GovernanceWorkflowType,
  PersonaRiskTolerance,
  RestoreConflictStatus,
  RoleChangeStatus,
  ScopedCopilotRunStatus,
} from "@/api/types";
import { toTitleCase } from "@/utils/governanceFormatting";

type Tone = "slate" | "brand" | "blue" | "emerald" | "amber" | "orange" | "red" | "purple";

const TONE_CLASSES: Record<Tone, string> = {
  slate: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  brand: "bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300",
  blue: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  emerald: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  amber: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  orange: "bg-orange-50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  red: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  purple: "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
};

function ToneBadge({
  label,
  tone,
}: {
  label: string;
  tone: Tone;
}) {
  return (
    <span className={clsx("badge", TONE_CLASSES[tone])}>
      {label}
    </span>
  );
}

const WORKFLOW_STATUS_TONES: Record<GovernanceWorkflowStatus, Tone> = {
  draft: "slate",
  analyzing: "blue",
  waiting_approval: "amber",
  approved: "emerald",
  executing: "brand",
  canary: "purple",
  grace_period: "orange",
  verifying: "blue",
  completed: "emerald",
  failed: "red",
  compensating: "orange",
  restored: "emerald",
  cancelled: "slate",
};

const WORKFLOW_TYPE_TONES: Record<GovernanceWorkflowType, Tone> = {
  least_privilege_migration: "purple",
  continuous_drift: "orange",
  jit_access: "blue",
  incident_containment: "red",
  access_review: "blue",
  restore: "amber",
};

const EVIDENCE_TONES: Record<EvidenceCoverageStatus, Tone> = {
  covered: "emerald",
  partial: "amber",
  missing: "red",
  expired: "orange",
};

const PERSONA_TONES: Record<PersonaRiskTolerance, Tone> = {
  strict: "emerald",
  balanced: "blue",
  expedited: "orange",
};

const ROLE_DIFF_TONES: Record<RoleChangeStatus, Tone> = {
  proposed: "amber",
  approved: "brand",
  canary_running: "blue",
  canary_failed: "red",
  rolled_back: "orange",
  completed: "emerald",
};

const RESTORE_CONFLICT_TONES: Record<RestoreConflictStatus, Tone> = {
  open: "red",
  in_review: "brand",
  accepted_risk: "orange",
  resolved: "emerald",
};

const CONNECTOR_HEALTH_TONES: Record<GovernanceConnectorHealth, Tone> = {
  healthy: "emerald",
  warning: "amber",
  degraded: "orange",
  offline: "red",
};

const CONNECTOR_MODE_TONES: Record<GovernanceConnectorSyncMode, Tone> = {
  scheduled: "blue",
  manual: "slate",
  paused: "orange",
};

const COPILOT_TONES: Record<ScopedCopilotRunStatus, Tone> = {
  queued: "amber",
  running: "brand",
  completed: "emerald",
  failed: "red",
};

export function WorkflowStatusBadge({ status }: { status: GovernanceWorkflowStatus }) {
  return <ToneBadge label={toTitleCase(status)} tone={WORKFLOW_STATUS_TONES[status]} />;
}

export function WorkflowTypeBadge({ type }: { type: GovernanceWorkflowType }) {
  return <ToneBadge label={toTitleCase(type)} tone={WORKFLOW_TYPE_TONES[type]} />;
}

export function CoverageBadge({ status }: { status: EvidenceCoverageStatus }) {
  return <ToneBadge label={toTitleCase(status)} tone={EVIDENCE_TONES[status]} />;
}

export function PersonaRiskBadge({ value }: { value: PersonaRiskTolerance }) {
  return <ToneBadge label={toTitleCase(value)} tone={PERSONA_TONES[value]} />;
}

export function RoleDiffStatusBadge({ status }: { status: RoleChangeStatus }) {
  return <ToneBadge label={toTitleCase(status)} tone={ROLE_DIFF_TONES[status]} />;
}

export function RestoreConflictStatusBadge({ status }: { status: RestoreConflictStatus }) {
  return <ToneBadge label={toTitleCase(status)} tone={RESTORE_CONFLICT_TONES[status]} />;
}

export function ConnectorHealthBadge({ health }: { health: GovernanceConnectorHealth }) {
  return <ToneBadge label={toTitleCase(health)} tone={CONNECTOR_HEALTH_TONES[health]} />;
}

export function ConnectorSyncModeBadge({ mode }: { mode: GovernanceConnectorSyncMode }) {
  return <ToneBadge label={toTitleCase(mode)} tone={CONNECTOR_MODE_TONES[mode]} />;
}

export function CopilotRunStatusBadge({ status }: { status: ScopedCopilotRunStatus }) {
  return <ToneBadge label={toTitleCase(status)} tone={COPILOT_TONES[status]} />;
}
