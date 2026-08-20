import { severityClass, statusClass } from '../utils/format'

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={`inline-flex rounded border px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide ${severityClass(severity)}`}>
      {severity}
    </span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex rounded px-2 py-0.5 text-[11px] font-semibold ${statusClass(status)}`}>
      {status}
    </span>
  )
}
