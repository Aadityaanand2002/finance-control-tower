import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../services/api'
import type { Dashboard } from '../types'
import { KpiCard } from '../components/KpiCard'
import { SeverityBadge, StatusBadge } from '../components/Badges'
import { formatINR, formatINRCompact, formatDate } from '../utils/format'

const PIE_COLORS = ['#528ff0', '#1fad6c', '#e34848', '#f37a2d', '#e5a100', '#6b6b80', '#7eb0f5']

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    api
      .dashboard()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const onRefresh = () => load()
    window.addEventListener('fct:refresh', onRefresh)
    return () => window.removeEventListener('fct:refresh', onRefresh)
  }, [])

  if (loading && !data) {
    return <p className="text-sm text-[var(--color-ink-muted)]">Loading…</p>
  }
  if (error && !data) return <ErrorBox message={error} onRetry={load} />
  if (!data) return null

  const statusData = Object.entries(data.settlement_status_distribution).map(([name, value]) => ({
    name,
    value,
  }))
  const sevData = Object.entries(data.exception_severity_distribution).map(([name, value]) => ({
    name,
    value,
  }))

  return (
    <div className="space-y-6">
      <div className="rzp-card p-5 flex flex-wrap items-center justify-between gap-4 border-l-4 border-l-[var(--color-rzp)]">
        <div>
          <div className="section-label text-[var(--color-rzp)]">Unreconciled exposure</div>
          <div className="mt-1 text-[28px] font-extrabold tracking-tight text-[var(--color-navy)]">
            {formatINRCompact(data.unreconciled_amount)}
          </div>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)] font-medium">
            {data.active_exceptions} open exceptions · {data.high_risk_exceptions} high risk ·{' '}
            {data.reconciliation_percentage}% reconciled
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/exceptions" className="rzp-btn-primary px-4 py-2">
            Review exceptions
          </Link>
          <Link to="/reconciliation" className="rzp-btn-secondary px-4 py-2">
            View reconciliation
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {['Detect', 'Explain', 'Prioritize', 'Recommend', 'Approve', 'Audit'].map((step, i) => (
          <span key={step} className="inline-flex items-center gap-1.5 text-[12px] text-[var(--color-ink-muted)]">
            {i > 0 && <span className="text-[#d0d4db]">/</span>}
            <span className="rounded border border-[var(--color-border)] bg-white px-2 py-0.5 font-semibold text-[var(--color-navy)]">
              {step}
            </span>
          </span>
        ))}
      </div>

      <section className="rzp-card p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="section-label">Financial overview</h2>
          <span className="text-[11px] font-semibold text-[var(--color-ink-muted)]">
            Live control metrics
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KpiCard label="Total Payments" value={data.total_payments} compact />
          <KpiCard label="Total Settled" value={data.total_settled} tone="success" compact />
          <KpiCard label="Pending Settlement" value={data.pending_settlement} tone="warn" compact />
          <KpiCard label="Unreconciled" value={data.unreconciled_amount} tone="danger" compact />
          <KpiCard label="Active Exceptions" value={data.active_exceptions} kind="count" />
          <KpiCard label="High Risk" value={data.high_risk_exceptions} kind="count" tone="danger" />
          <KpiCard label="Expected Cash" value={data.expected_cash_position} compact />
          <KpiCard label="At-Risk Amount" value={data.recoverable_at_risk} tone="warn" compact />
        </div>
      </section>

      <div className="grid lg:grid-cols-3 gap-4">
        <Panel title="Cash position trend">
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.cash_position_trend}>
                <defs>
                  <linearGradient id="cashFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#528ff0" stopOpacity={0.28} />
                    <stop offset="100%" stopColor="#528ff0" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis
                  tickFormatter={(v) => `₹${(v / 100 / 100000).toFixed(1)}L`}
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  width={48}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip formatter={(v) => formatINR(Number(v))} />
                <Area type="monotone" dataKey="cash" stroke="#528ff0" fill="url(#cashFill)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Settlement status">
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={46} outerRadius={72} paddingAngle={2}>
                  {statusData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Exception severity">
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sevData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#94a3b8' }} width={28} axisLine={false} tickLine={false} />
                <Tooltip />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {sevData.map((d, i) => (
                    <Cell
                      key={i}
                      fill={
                        d.name === 'critical'
                          ? '#e34848'
                          : d.name === 'high'
                            ? '#f37a2d'
                            : d.name === 'medium'
                              ? '#e5a100'
                              : '#6b6b80'
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Panel title="High-priority exceptions">
          <ul className="divide-y divide-[#f0f2f5]">
            {data.recent_high_priority_exceptions.map((e) => (
              <li key={e.id} className="py-3 flex items-start justify-between gap-3 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <Link to={`/exceptions/${e.id}`} className="text-[13.5px] font-bold text-[var(--color-rzp)] hover:underline">
                    {e.entity_id}
                  </Link>
                  <div className="text-[12.5px] text-[var(--color-ink-muted)] mt-0.5 line-clamp-2">{e.explanation}</div>
                </div>
                <div className="text-right shrink-0 space-y-1">
                  <SeverityBadge severity={e.severity} />
                  <div className="text-[13px] font-extrabold text-[var(--color-navy)] tabular-nums">{formatINR(e.amount_affected)}</div>
                </div>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Activity">
          <ul className="space-y-2.5 max-h-72 overflow-auto">
            {data.activity_stream.map((a) => (
              <li key={a.id} className="flex gap-3 text-[13px] items-start">
                <span className="text-[11px] text-[var(--color-ink-muted)] w-28 shrink-0 pt-0.5 tabular-nums">
                  {formatDate(a.created_at)}
                </span>
                <StatusBadge status={a.event_type} />
                <span className="text-[var(--color-ink)] leading-snug">{a.message}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rzp-card p-4">
      <h2 className="section-label mb-3">{title}</h2>
      {children}
    </section>
  )
}

function ErrorBox({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="rzp-card border-rose-200 bg-rose-50 p-4 text-sm">
      <p className="font-semibold text-rose-800">Unable to load control center</p>
      <p className="text-rose-700 mt-1">{message}</p>
      <button onClick={onRetry} className="rzp-btn-primary mt-3 px-3 py-1.5 text-xs">
        Retry
      </button>
    </div>
  )
}
