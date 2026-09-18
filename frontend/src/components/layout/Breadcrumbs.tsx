import { Link, useLocation, useParams } from "react-router-dom";
import { Fragment } from "react";
import { useProjectContext } from "@/store/projectContext";
import { SEGMENT_LABELS } from "./pageRegistry";

function humanize(segment: string): string {
  if (SEGMENT_LABELS[segment]) return SEGMENT_LABELS[segment];
  // Detail IDs (rec-001, id-0004, drift-003, guids…) → shortened label.
  if (/^[0-9a-f-]{8,}$/i.test(segment) || /-\d+$/.test(segment)) {
    return "Detail";
  }
  return segment
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Breadcrumb trail derived from the URL under /projects/:projectId/…
 * Always starts from the project, then the page, then any sub-view.
 */
export function Breadcrumbs() {
  const location = useLocation();
  const { projectId } = useParams();
  const { project } = useProjectContext();

  const base = `/projects/${projectId}`;
  const afterBase = location.pathname.startsWith(base)
    ? location.pathname.slice(base.length)
    : "";
  const segments = afterBase.split("/").filter(Boolean);

  const crumbs: { label: string; to?: string }[] = [
    { label: project?.name ?? "Project", to: `${base}/dashboard` },
  ];

  let acc = base;
  segments.forEach((seg, idx) => {
    acc += `/${seg}`;
    const isLast = idx === segments.length - 1;
    crumbs.push({ label: humanize(seg), to: isLast ? undefined : acc });
  });

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-[13px]">
      <Link
        to="/projects"
        className="text-slate-400 transition-colors hover:text-brand-600 dark:text-slate-500 dark:hover:text-brand-400"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75" />
        </svg>
      </Link>
      {crumbs.map((c, idx) => {
        const isLast = idx === crumbs.length - 1;
        return (
          <Fragment key={idx}>
            <svg className="h-3.5 w-3.5 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            {c.to && !isLast ? (
              <Link
                to={c.to}
                className="font-medium text-slate-500 transition-colors hover:text-brand-600 dark:text-slate-400 dark:hover:text-brand-400"
              >
                {c.label}
              </Link>
            ) : (
              <span className="font-semibold text-slate-700 dark:text-slate-200">
                {c.label}
              </span>
            )}
          </Fragment>
        );
      })}
    </nav>
  );
}
