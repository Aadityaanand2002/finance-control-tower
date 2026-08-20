import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import type { Exception } from '../types'
import { SeverityBadge, StatusBadge } from '../components/Badges'
import { formatINR, formatDate } from '../utils/format'

export default function ExceptionsPage() {
  const [rows, setRows] = useState<Exception[]>([])
  const [error, setError] = useState<string | null>(null)
  const [severity, setSeverity] = useState('')
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [minAmount, setMinAmount] = useState('')

  const load = () => {
    const params: Record<string, string> = {}
    if (severity) params.severity = severity
    if (status) params.status = status
    if (type) params.type = type
    if (minAmount) params.min_amount = String(Math.round(Number(minAmount) * 100))
    api
      .exceptions(params)
      .then(setRows)
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
    const onRefresh = () => load()
    window.addEventListener('fct:refresh', onRefresh)
    return () => window.removeEventListener('fct:refresh', onRefresh)
  }, [severity, status, type, minAmount])

  const types = useMemo(() => Array.from(new Set(rows.map((r) => r.type))), [rows])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 rzp-card p-3">
        <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="select-pro">
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="select-pro">
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="under_review">Under review</option>
          <option value="action_approved">Action approved</option>
          <option value="rejected">Rejected</option>
          <option value="resolved">Resolved</option>
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)} className="select-pro">
          <option value="">All types</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          type="number"
          placeholder="Min amount ₹"
          value={minAmount}
          onChange={(e) => setMinAmount(e.target.value)}
          className="input-pro w-36"
        />
      </div>

      {error && <p className="text-sm text-rose-700">{error}</p>}

      <div className="rzp-card overflow-hidden">
        {rows.length === 0 ? (
          <div className="p-10 text-center text-sm text-[var(--color-ink-muted)]">
            No exceptions match these filters.
          </div>
        ) : (
          <div className="overflow-auto">
            <table className="table-pro">
              <thead>
                <tr>
                  <th>Entity</th>
                  <th>Type</th>
                  <th>Severity</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr key={e.id}>
                    <td>
                      <Link to={`/exceptions/${e.id}`} className="font-semibold text-[var(--color-rzp)] hover:underline">
                        {e.entity_id}
                      </Link>
                      <div className="text-[11.5px] text-[var(--color-ink-muted)] mt-0.5">{e.id}</div>
                    </td>
                    <td className="text-[var(--color-ink-muted)]">{e.type}</td>
                    <td>
                      <SeverityBadge severity={e.severity} />
                    </td>
                    <td className="font-semibold tabular-nums">{formatINR(e.amount_affected)}</td>
                    <td>
                      <StatusBadge status={e.status} />
                    </td>
                    <td className="tabular-nums text-[var(--color-ink-muted)]">{e.priority_score.toFixed(1)}</td>
                    <td className="text-[var(--color-ink-muted)] whitespace-nowrap">{formatDate(e.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
