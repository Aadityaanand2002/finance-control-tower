import { formatINR, formatINRCompact } from '../utils/format'

type Props = {
  label: string
  value: number
  hint?: string
  tone?: 'default' | 'danger' | 'warn' | 'success'
  compact?: boolean
  kind?: 'money' | 'count'
}

export function KpiCard({ label, value, hint, tone = 'default', compact, kind = 'money' }: Props) {
  const bar =
    tone === 'danger'
      ? 'bg-[#e34848]'
      : tone === 'warn'
        ? 'bg-[#f37a2d]'
        : tone === 'success'
          ? 'bg-[#1fad6c]'
          : 'bg-[#528ff0]'

  const display =
    kind === 'count' ? String(value) : compact ? formatINRCompact(value) : formatINR(value)

  return (
    <div className="relative overflow-hidden rounded border border-[var(--color-border)] bg-[#fafbfc] p-3.5">
      <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${bar}`} />
      <div className="section-label pl-1">{label}</div>
      <div className="mt-2 pl-1 text-[20px] font-extrabold tracking-tight tabular-nums text-[var(--color-navy)]">
        {display}
      </div>
      {hint && <div className="mt-1 pl-1 text-xs text-[var(--color-ink-muted)] font-medium">{hint}</div>}
    </div>
  )
}
