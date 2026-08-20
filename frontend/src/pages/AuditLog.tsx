import { useEffect, useState } from 'react'
import { api } from '../services/api'
import type { AuditLog } from '../types'
import { formatDate } from '../utils/format'

export default function AuditLogPage() {
  const [rows, setRows] = useState<AuditLog[]>([])
  const [entityId, setEntityId] = useState('')
  const [user, setUser] = useState('')
  const [decision, setDecision] = useState('')
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    const params: Record<string, string> = {}
    if (entityId) params.entity_id = entityId
    if (user) params.user = user
    if (decision) params.decision = decision
    api
      .auditLog(params)
      .then(setRows)
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
    const onRefresh = () => load()
    window.addEventListener('fct:refresh', onRefresh)
    return () => window.removeEventListener('fct:refresh', onRefresh)
  }, [entityId, user, decision])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 rzp-card p-3">
        <input
          placeholder="Entity ID (e.g. set_1024)"
          value={entityId}
          onChange={(e) => setEntityId(e.target.value)}
          className="input-pro"
        />
        <input
          placeholder="User"
          value={user}
          onChange={(e) => setUser(e.target.value)}
          className="input-pro"
        />
        <select value={decision} onChange={(e) => setDecision(e.target.value)} className="select-pro">
          <option value="">All decisions</option>
          <option value="Approved">Approved</option>
          <option value="Rejected">Rejected</option>
          <option value="Reviewed">Reviewed</option>
          <option value="Resolved">Resolved</option>
        </select>
      </div>

      {error && <p className="text-sm text-[#e34848]">{error}</p>}

      <div className="rzp-card overflow-hidden">
        {rows.length === 0 ? (
          <div className="p-8 text-center text-sm text-[var(--color-ink-muted)]">
            No audit entries match these filters yet. Approve an exception action to create the first record.
          </div>
        ) : (
          <div className="overflow-auto">
            <table className="table-pro min-w-full">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Entity</th>
                  <th>AI Recommendation</th>
                  <th>User Decision</th>
                  <th>Action</th>
                  <th>Previous</th>
                  <th>New</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="whitespace-nowrap">{formatDate(r.timestamp)}</td>
                    <td>{r.performed_by}</td>
                    <td className="font-bold text-[var(--color-navy)]">{r.entity_id || '—'}</td>
                    <td className="max-w-xs truncate" title={r.ai_recommendation || ''}>
                      {r.ai_recommendation || '—'}
                    </td>
                    <td>{r.user_decision || '—'}</td>
                    <td>{r.action}</td>
                    <td>{r.old_state || '—'}</td>
                    <td>{r.new_state || '—'}</td>
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
