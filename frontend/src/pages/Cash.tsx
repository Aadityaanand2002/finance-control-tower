import { useEffect, useState } from 'react'
import { api } from '../services/api'
import type { CashPosition } from '../types'
import { formatINR } from '../utils/format'

export default function CashPositionPage() {
  const [data, setData] = useState<CashPosition | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = () =>
    api
      .cash()
      .then(setData)
      .catch((e) => setError(e.message))

  useEffect(() => {
    load()
    const onRefresh = () => load()
    window.addEventListener('fct:refresh', onRefresh)
    return () => window.removeEventListener('fct:refresh', onRefresh)
  }, [])

  if (error) return <p className="text-sm text-[#e34848]">{error}</p>
  if (!data) return <p className="text-sm text-[var(--color-ink-muted)]">Calculating cash position…</p>

  const rows = [
    { label: 'Available Cash', value: data.available_cash, sign: '+' },
    { label: 'Expected Settlements', value: data.expected_settlements, sign: '+' },
    { label: 'Pending Receivables', value: data.pending_receivables, sign: '+' },
    { label: 'Upcoming Expenses', value: data.upcoming_expenses, sign: '−' },
    { label: 'Outstanding Refunds', value: data.outstanding_refunds, sign: '−' },
    { label: 'At-Risk / Unreconciled', value: data.at_risk_unreconciled, sign: '−' },
  ]

  return (
    <div className="space-y-5 max-w-3xl">
      <div
        className={`rzp-card p-5 border-l-4 ${
          data.projected_net_cash < 0
            ? 'border-l-[#e34848] bg-[#fef5f5]'
            : 'border-l-[var(--color-rzp)] bg-[var(--color-rzp-soft)]'
        }`}
      >
        <div className="section-label">Projected available amount</div>
        <div className="text-[32px] font-extrabold tracking-tight mt-1 text-[var(--color-navy)]">
          {formatINR(data.projected_net_cash)}
        </div>
        <p className="mt-1 text-sm text-[var(--color-ink-muted)] font-medium">{data.control_adjusted_label}</p>
        {data.projected_net_cash < 0 && (
          <p className="mt-2 text-sm text-[#e34848] font-medium">
            Cash risk: upcoming expenses and at-risk amounts exceed control-adjusted inflows.
          </p>
        )}
      </div>

      <div className="rzp-card overflow-hidden">
        <table className="w-full text-sm">
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-b border-[#f0f2f5]">
                <td className="px-4 py-3">
                  <span className="text-[var(--color-ink-muted)] mr-2 font-semibold">{r.sign}</span>
                  {r.label}
                </td>
                <td className="px-4 py-3 text-right font-bold tabular-nums text-[var(--color-navy)]">
                  {formatINR(r.value)}
                </td>
              </tr>
            ))}
            <tr className="bg-[#fafbfc] font-extrabold">
              <td className="px-4 py-3 text-[var(--color-navy)]">= Projected Net Cash</td>
              <td className="px-4 py-3 text-right tabular-nums text-[var(--color-navy)]">
                {formatINR(data.projected_net_cash)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="rzp-card p-4">
        <h2 className="section-label mb-2">Transparent calculation</h2>
        <ol className="text-sm space-y-1.5 list-decimal pl-4 text-[var(--color-ink)] font-medium">
          {data.calculation_steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      </div>
    </div>
  )
}
