// frontend/src/utils/formatRelativeTime.ts

/**
 * Format an ISO date string as a human-readable relative time.
 * Returns "Never" for null/undefined inputs.
 * Falls back to toLocaleDateString() for dates older than 30 days.
 */
export function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "Never";

  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "Invalid date";

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffMs < 0) return "In the future";
  if (diffDay > 30) return date.toLocaleDateString();
  if (diffDay > 0) return `${diffDay}d ago`;
  if (diffHour > 0) return `${diffHour}h ago`;
  if (diffMin > 0) return `${diffMin}m ago`;
  return "Just now";
}
