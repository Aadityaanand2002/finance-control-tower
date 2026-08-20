import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import type { ReconciliationMatch } from '../types'
import { StatusBadge } from '../components/Badges'
import { formatINR } from '../utils/format'
import { ArrowRight } from 'lucide-react'

export default function ReconciliationPage() {
  const [rows, setRows] = useState<ReconciliationMatch[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = () => api.reconciliation().then(setRows).catch((e) => setMessage(e.message))

  useEffect(() => {
    load()
    const onRefresh = () => load()
    window.addEventListener('fct:refresh', onRefresh)
    return () => window.removeEventListener('fct:refresh', onRefresh)
  }, [])

  async function run() {
    setBusy(true)
    try {
      const res = (await api.runReconciliation()) as { message: string }
      setMessage(res.message)
      await load()
      window.dispatchEvent(new Event('fct:refresh'))
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Reconciliation failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-[var(--color-ink-muted)] font-medium">
          Payment → Settlement → Bank matching
        </p>
        <button onClick={run} disabled={busy} className="rzp-btn-primary px-3 py-2 disabled:opacity-50">
          {busy ? 'Running…' : 'Run reconciliation'}
        </button>
      </div>
      {message && <p className="text-sm rzp-card px-3 py-2 font-medium">{message}</p>}

      <div className="space-y-3">
        {rows.map((r) => (
          <div key={r.settlement_id} className="rzp-card p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <span className="font-extrabold text-[var(--color-navy)]">{r.settlement_id}</span>
              <StatusBadge status={r.status} />
            </div>
            <div className="flex flex-col md:flex-row md:items-center gap-2 text-sm">
              <Node label="Payments" value={r.payment_ids.join(', ') || '—'} />
              <ArrowRight className="hidden md:block h-4 w-4 text-[#c0c4cc]" />
              <Node label="Settlement" value={`${formatINR(r.expected_amount)} expected`} />
              <ArrowRight className="hidden md:block h-4 w-4 text-[#c0c4cc]" />
              <Node
                label="Bank"
                value={r.bank_ids.length ? `${formatINR(r.actual_amount)} · ${r.bank_ids.join(', ')}` : 'Missing'}
              />
            </div>
            <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <Stat label="Expected" value={formatINR(r.expected_amount)} />
              <Stat label="Actual" value={formatINR(r.actual_amount)} />
              <Stat label="Difference" value={formatINR(r.difference)} />
              <Stat label="Confidence" value={`${Math.round(r.confidence * 100)}%`} />
            </div>
            {r.explanation && <p className="mt-2 text-xs text-[var(--color-ink-muted)]">{r.explanation}</p>}
            <Link
              to="/exceptions"
              className="inline-block mt-2 text-xs font-bold text-[var(--color-rzp)] hover:text-[var(--color-rzp-dark)]"
            >
              View related exceptions
            </Link>
          </div>
        ))}
      </div>
    </div>
  )
}

function Node({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex-1 rounded border border-[var(--color-border)] bg-[#fafbfc] px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide font-bold text-[var(--color-ink-muted)]">{label}</div>
      <div className="font-semibold break-all text-[var(--color-navy)]">{value}</div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--color-border)] bg-[#fafbfc] px-2 py-1.5">
      <div className="text-[var(--color-ink-muted)] font-semibold">{label}</div>
      <div className="font-extrabold text-[var(--color-navy)] tabular-nums">{value}</div>
    </div>
  )
}
