import { useState } from "react";
import {
  useProjectMembers,
  useInviteMember,
  useUpdateMemberRole,
  useRemoveMember,
} from "@/api/projectHooks";
import { useProjectContext } from "@/store/projectContext";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { MotionItem, MotionStagger } from "@/components/common/motion";
import type { ProjectMember } from "@/api/types";

function RoleBadge({ role }: { role: string }) {
  const styles: Record<string, string> = {
    admin:
      "bg-brand-50 text-brand-700 dark:bg-brand-900/20 dark:text-brand-300",
    operator:
      "bg-sky-50 text-sky-700 dark:bg-sky-900/20 dark:text-sky-300",
    viewer:
      "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
    owner:
      "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400",
  };
  return (
    <span className={`badge ${styles[role] ?? styles.viewer}`}>{role}</span>
  );
}

function MemberRow({
  member,
  projectId,
  canManage,
}: {
  member: ProjectMember;
  projectId: string;
  canManage: boolean;
}) {
  const updateRole = useUpdateMemberRole(projectId);
  const removeMember = useRemoveMember(projectId);
  const [editing, setEditing] = useState(false);
  const [newRole, setNewRole] = useState(member.role);

  function handleSaveRole() {
    updateRole.mutate(
      { memberId: member.id, role: newRole },
      { onSuccess: () => setEditing(false) },
    );
  }

  return (
    <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5 transition-colors last:border-b-0 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/60">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-xs font-bold text-brand-700 dark:bg-brand-900/30 dark:text-brand-300">
          {member.email.charAt(0).toUpperCase()}
        </div>
        <div>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
            {member.email}
          </p>
          {member.status === "pending" && (
            <span className="text-[10px] font-medium text-amber-600 dark:text-amber-400">
              Pending invite
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {editing ? (
          <>
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value as typeof newRole)}
              className="input-base text-sm"
              aria-label="Member role"
            >
              <option value="viewer">Viewer</option>
              <option value="operator">Operator</option>
              <option value="admin">Admin</option>
            </select>
            <button
              onClick={handleSaveRole}
              disabled={updateRole.isPending}
              className="btn-primary text-xs"
            >
              Save
            </button>
            <button
              onClick={() => {
                setEditing(false);
                setNewRole(member.role);
              }}
              className="btn-secondary text-xs"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <RoleBadge role={member.role} />
            {canManage && member.role !== "owner" && (
              <div className="flex gap-1">
                <button
                  onClick={() => setEditing(true)}
                  className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
                  title="Edit role"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </button>
                <button
                  onClick={() => removeMember.mutate(member.id)}
                  disabled={removeMember.isPending}
                  className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20 dark:hover:text-red-400"
                  title="Remove member"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function ProjectMembersPage() {
  const { projectId, project } = useProjectContext();
  const { data, isLoading } = useProjectMembers(projectId);
  const members = data?.members;
  const currentUserRole = data?.current_user_role;
  const canManageMembers = currentUserRole === "owner" || currentUserRole === "admin";
  const inviteMember = useInviteMember(projectId);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");
  const [error, setError] = useState<string | null>(null);

  function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setError(null);
    inviteMember.mutate(
      { email: email.trim(), role },
      {
        onSuccess: () => {
          setEmail("");
          setRole("viewer");
        },
        onError: (err) =>
          setError(
            err instanceof Error ? err.message : "Failed to invite member.",
          ),
      },
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="eyebrow">Manage</p>
        <h1 className="page-title mt-1">Team Members</h1>
        <p className="page-subtitle">
          Manage who has access to{" "}
          <span className="font-medium text-slate-700 dark:text-slate-300">
            {project.name}
          </span>
        </p>
      </div>

      {/* Invite form — visible only to owners and admins */}
      {canManageMembers && (
        <MotionItem>
        <div className="card p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Access Control</p>
              <h2 className="section-title mt-1">Invite Member</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Add a teammate with project-scoped permissions.
              </p>
            </div>
          </div>
          <form
            onSubmit={handleInvite}
            className="mt-4 flex flex-wrap items-end gap-3"
          >
            <div className="flex-1">
              <label
                htmlFor="invite-email"
                className="block text-sm font-semibold text-slate-700 dark:text-slate-300"
              >
                Email Address
              </label>
              <input
                id="invite-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="colleague@example.com"
                className="input-base mt-1.5 block w-full"
                required
              />
            </div>
            <div>
              <label
                htmlFor="invite-role"
                className="block text-sm font-semibold text-slate-700 dark:text-slate-300"
              >
                Role
              </label>
              <select
                id="invite-role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="input-base mt-1.5 block"
              >
                <option value="viewer">Viewer</option>
                <option value="operator">Operator</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={inviteMember.isPending || !email.trim()}
              className="btn-primary"
            >
              {inviteMember.isPending ? "Inviting..." : "Invite"}
            </button>
          </form>
          {error && (
            <p className="mt-3 text-sm text-red-600 dark:text-red-400">
              {error}
            </p>
          )}
        </div>
        </MotionItem>
      )}

      {/* Members list */}
      <div className="card">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 dark:border-slate-800">
          <div>
            <p className="eyebrow">Directory</p>
            <h2 className="section-title mt-1">Members</h2>
          </div>
          {members && (
            <AnimatedNumber
              value={members.length}
              className="text-2xl font-bold tabular-nums text-slate-900 dark:text-white"
            />
          )}
        </div>

        {isLoading ? (
          <div className="space-y-3 p-5">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="skeleton h-12 rounded-xl"
              />
            ))}
          </div>
        ) : members && members.length > 0 ? (
          <MotionStagger>
            {members.map((m) => (
              <MotionItem key={m.id}>
                <MemberRow
                  member={m}
                  projectId={projectId}
                  canManage={canManageMembers}
                />
              </MotionItem>
            ))}
          </MotionStagger>
        ) : (
          <div className="px-5 py-8 text-center text-sm text-slate-400 dark:text-slate-500">
            No team members yet. Invite someone above.
          </div>
        )}
      </div>
    </div>
  );
}
