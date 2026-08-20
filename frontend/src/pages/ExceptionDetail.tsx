import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../services/api'
import type { AIAnalysisResult, ExceptionDetail } from '../types'
import { SeverityBadge, StatusBadge } from '../components/Badges'
import { formatINR, formatDate } from '../utils/format'
import { ArrowDown, CheckCircle2, XCircle, Eye, FileText } from 'lucide-react'

export default function ExceptionDetailPage() {
  const { id } = useParams()
  const [data, setData] = useState<ExceptionDetail | null>(null)
  const [analysis, setAnalysis] = useState<AIAnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<string | null>(null)

  const load = () => {
    if (!id) return
    api
      .exceptionDetail(id)
      .then(setData)
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
  }, [id])

  async function act(label: string, fn: () => Promise<unknown>) {
    if (!id) return
    setBusy(label)
    try {
      await fn()
      setConfirm(`${label} recorded. Application state updated.`)
      load()
      window.dispatchEvent(new Event('fct:refresh'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed')
    } finally {
      setBusy(null)
      setTimeout(() => setConfirm(null), 4000)
    }
  }

  async function runAnalyze() {
    if (!id) return
    setBusy('analyze')
    try {
      const res = await api.analyze(id)
      setAnalysis(res)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setBusy(null)
    }
  }

  if (error && !data) {
    return <p className="text-red-700 text-sm">{error}</p>
  }
  if (!data) return <p className="text-sm text-[var(--color-ink-muted)]">Loading investigation…</p>

  const exc = data.exception
  const reasons = Array.isArray(exc.priority_reasons) ? exc.priority_reasons : []
  const pattern = exc.pattern_info as Record<string, unknown> | null | undefined

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/exceptions" className="text-xs text-[var(--color-rzp)] hover:underline">
            ← All exceptions
          </Link>
          <h1 className="text-[28px] font-bold tracking-tight mt-1">Settlement {exc.entity_id.toUpperCase()}</h1>
          <div className="mt-2 flex flex-wrap gap-2 items-center">
            <SeverityBadge severity={exc.severity} />
            <StatusBadge status={exc.status} />
            <span className="text-sm text-[var(--color-ink-muted)]">Exception {exc.id}</span>
          </div>
        </div>
        <div className="text-right rzp-card px-4 py-3">
          <div className="section-label text-rose-600">Amount at risk</div>
          <div className="text-[26px] font-bold tracking-tight text-rose-600 tabular-nums">
            {formatINR(exc.amount_affected)}
          </div>
        </div>
      </div>

      {confirm && (
        <div className="rounded-lg border border-blue-200 bg-[var(--color-rzp-soft)] px-3 py-2 text-sm text-[var(--color-navy)]">{confirm}</div>
      )}
      {analysis?.fallback_used && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
          {analysis.fallback_message || 'AI service unavailable. Running deterministic financial analysis.'}
        </div>
      )}

      <div className="grid md:grid-cols-3 gap-3">
        <Metric label="Expected" value={formatINR(exc.expected_value)} />
        <Metric label="Actual" value={formatINR(exc.actual_value)} />
        <Metric label="Difference" value={formatINR(exc.amount_affected)} danger />
      </div>

      <section className="rzp-card p-4">
        <h2 className="text-[13px] font-semibold mb-4">Transaction chain</h2>
        <div className="flex flex-col md:flex-row items-stretch gap-3">
          <ChainCard title="Payment" items={data.payments.map((p) => `${p.id} · ${formatINR(p.amount)}`)} />
          <div className="grid place-items-center text-[var(--color-ink-muted)]">
            <ArrowDown className="md:rotate-[-90deg]" />
          </div>
          <ChainCard
            title="Settlement"
            items={
              data.settlement
                ? [
                    data.settlement.id,
                    `Expected ${formatINR(data.settlement.expected_amount)}`,
                    data.settlement.reconciliation_status || '',
                  ]
                : ['—']
            }
          />
          <div className="grid place-items-center text-[var(--color-ink-muted)]">
            <ArrowDown className="md:rotate-[-90deg]" />
          </div>
          <ChainCard
            title="Bank"
            items={
              data.bank_transactions.length
                ? data.bank_transactions.map((b) => `${b.id} · ${formatINR(b.amount)} · ${b.utr || ''}`)
                : ['Missing bank entry']
            }
          />
        </div>
      </section>

      <div className="grid lg:grid-cols-2 gap-4">
        <section className="rzp-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-[13px] font-semibold">AI analysis</h2>
            <button
              onClick={runAnalyze}
              disabled={!!busy}
              className="text-xs rounded-lg border px-2.5 py-1 hover:bg-slate-50 disabled:opacity-50"
            >
              {busy === 'analyze' ? 'Analyzing…' : 'Re-run AI analysis'}
            </button>
          </div>
          <p className="text-sm leading-relaxed">{analysis?.summary || exc.explanation}</p>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-xs text-[var(--color-ink-muted)]">Root cause</div>
              <div className="font-medium">{analysis?.root_cause || exc.root_cause}</div>
            </div>
            <div>
              <div className="text-xs text-[var(--color-ink-muted)]">Confidence</div>
              <div className="font-medium">{Math.round((analysis?.confidence ?? exc.confidence) * 100)}%</div>
            </div>
          </div>
          <div>
            <div className="text-xs text-[var(--color-ink-muted)] mb-1">Why this matters</div>
            <ul className="text-sm space-y-1 list-disc pl-4">
              {(analysis?.reasoning || exc.reasoning || []).map((r, i) => (
                <li key={i}>{String(r)}</li>
              ))}
            </ul>
          </div>
          {pattern && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm">
              <div className="font-semibold text-amber-900">Why is this happening?</div>
              <p className="mt-1">{String(pattern.label || 'Recurring discrepancy pattern detected.')}</p>
              <ul className="mt-2 text-xs space-y-1 text-amber-900">
                <li>Occurrences: {String(pattern.occurrences)}</li>
                <li>Total historical impact: {formatINR(Number(pattern.total_historical_impact || 0))}</li>
                <li>Average discrepancy: {formatINR(Number(pattern.average_discrepancy || 0))}</li>
                <li>Likely root cause: {String(pattern.likely_root_cause)}</li>
              </ul>
            </div>
          )}
        </section>

        <section className="rzp-card p-4 space-y-3">
          <h2 className="text-[13px] font-semibold">Priority</h2>
          <p className="text-sm font-medium capitalize">{exc.severity} priority because:</p>
          <ul className="text-sm space-y-1 list-disc pl-4">
            {reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>

          <div className="pt-3 border-t">
            <h3 className="text-sm font-semibold">Recommended action</h3>
            <p className="mt-1 text-sm">{analysis?.recommended_action || exc.recommended_action}</p>
            <p className="mt-2 text-xs text-[var(--color-ink-muted)]">
              Human-in-the-loop: AI recommends → you approve → action is audited.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <ActionBtn icon={Eye} label="Review" busy={busy} onClick={() => act('Review', () => api.review(exc.id))} />
              <ActionBtn
                icon={CheckCircle2}
                label="Approve Action"
                primary
                busy={busy}
                onClick={() => act('Approve', () => api.approve(exc.id))}
              />
              <ActionBtn icon={XCircle} label="Reject" busy={busy} onClick={() => act('Reject', () => api.reject(exc.id))} />
              <ActionBtn
                icon={FileText}
                label="Generate Finance Request"
                busy={busy}
                onClick={() => act('Finance request', () => api.financeRequest(exc.id))}
              />
              <ActionBtn label="Mark Resolved" busy={busy} onClick={() => act('Resolve', () => api.resolve(exc.id))} />
            </div>
          </div>
        </section>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <section className="rzp-card p-4">
          <h2 className="text-[13px] font-semibold mb-3">Timeline</h2>
          <ol className="space-y-2">
            {data.timeline.map((t, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="text-xs text-[var(--color-ink-muted)] w-36 shrink-0">{formatDate(t.at)}</span>
                <StatusBadge status={t.kind} />
                <span>{t.label}</span>
              </li>
            ))}
          </ol>
        </section>
        <section className="rzp-card p-4">
          <h2 className="text-[13px] font-semibold mb-3">Audit trail</h2>
          <ul className="space-y-2 text-sm">
            {data.audit_trail.length === 0 && <li className="text-[var(--color-ink-muted)]">No actions yet.</li>}
            {data.audit_trail.map((a) => (
              <li key={a.id} className="border-b border-slate-100 pb-2">
                <div className="font-medium">
                  {formatDate(a.timestamp)} · {a.performed_by}
                </div>
                <div>
                  {a.action}
                  {a.old_state && a.new_state ? ` (${a.old_state} → ${a.new_state})` : ''}
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}

function Metric({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className={`rzp-card p-4 ${danger ? 'border-rose-200 bg-rose-50' : ''}`}>
      <div className="section-label">{label}</div>
      <div className={`mt-1 text-[22px] font-bold tracking-tight tabular-nums ${danger ? 'text-rose-600' : ''}`}>
        {value}
      </div>
    </div>
  )
}

function ChainCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="flex-1 rounded-lg border border-[var(--color-border)] bg-slate-50 p-3">
      <div className="text-xs font-semibold uppercase text-[var(--color-ink-muted)]">{title}</div>
      <ul className="mt-2 text-sm space-y-1">
        {items.map((it, i) => (
          <li key={i}>{it}</li>
        ))}
      </ul>
    </div>
  )
}

function ActionBtn({
  label,
  onClick,
  busy,
  primary,
  icon: Icon,
}: {
  label: string
  onClick: () => void
  busy: string | null
  primary?: boolean
  icon?: React.ComponentType<{ className?: string }>
}) {
  return (
    <button
      disabled={!!busy}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium disabled:opacity-50 ${
        primary ? 'rzp-btn-primary px-3 py-1.5' : 'rzp-btn-secondary px-3 py-1.5'
      }`}
    >
      {Icon && <Icon className="h-3.5 w-3.5" />}
      {busy === label ? '…' : label}
    </button>
  )
}
