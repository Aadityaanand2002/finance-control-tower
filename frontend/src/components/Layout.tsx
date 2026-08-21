import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  AlertTriangle,
  GitCompareArrows,
  Wallet,
  Bot,
  ScrollText,
  Play,
  RotateCcw,
  Sparkles,
  Menu,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '../services/api'

const nav = [
  { to: '/', label: 'Control Center', icon: LayoutDashboard },
  { to: '/exceptions', label: 'Exceptions', icon: AlertTriangle },
  { to: '/reconciliation', label: 'Reconciliation', icon: GitCompareArrows },
  { to: '/cash', label: 'Cash Impact', icon: Wallet },
  { to: '/copilot', label: 'AI Copilot', icon: Bot },
  { to: '/audit', label: 'Audit Trail', icon: ScrollText },
]

const titles: Record<string, { title: string; subtitle: string }> = {
  '/': {
    title: 'Control Center',
    subtitle: 'Exception exposure, reconciliation health, and control actions',
  },
  '/exceptions': {
    title: 'Exceptions',
    subtitle: 'Prioritized financial discrepancies requiring review',
  },
  '/reconciliation': {
    title: 'Reconciliation',
    subtitle: 'Payment → Settlement → Bank matching status',
  },
  '/cash': {
    title: 'Cash Impact',
    subtitle: 'Control-adjusted position after at-risk exposure',
  },
  '/copilot': {
    title: 'AI Copilot',
    subtitle: 'Ask questions grounded in live exception and ledger data',
  },
  '/audit': {
    title: 'Audit Trail',
    subtitle: 'AI recommendations and human decisions',
  },
}

export default function Layout() {
  const [busy, setBusy] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [mobileOpen, setMobileOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const headerMeta = useMemo(() => {
    if (location.pathname.startsWith('/exceptions/')) {
      return { title: 'Exception detail', subtitle: 'Investigation, AI analysis, and approval workflow' }
    }
    return titles[location.pathname] || titles['/']
  }, [location.pathname])

  async function run(label: string, fn: () => Promise<unknown>, then?: () => void) {
    setBusy(label)
    try {
      const res = (await fn()) as { message?: string }
      setToast(res?.message || `${label} complete`)
      then?.()
      window.dispatchEvent(new Event('fct:refresh'))
    } catch (e) {
      setToast(e instanceof Error ? e.message : 'Action failed')
    } finally {
      setBusy(null)
      setTimeout(() => setToast(null), 4000)
    }
  }

  const sidebar = (
    <aside className="flex h-full w-[232px] flex-col border-r border-[var(--color-border)] bg-white">
      <div className="px-4 py-4 border-b border-[var(--color-border)]">
        <Link to="/" className="flex items-center gap-2.5" onClick={() => setMobileOpen(false)}>
          {/* Razorpay-like geometric mark (not the official logo) */}
          <div className="relative h-8 w-8 shrink-0">
            <span className="absolute left-0 top-0 h-3.5 w-3.5 rounded-[2px] bg-[#528ff0]" />
            <span className="absolute right-0 top-0 h-3.5 w-3.5 rounded-[2px] bg-[#2b6de0]" />
            <span className="absolute left-0 bottom-0 h-3.5 w-3.5 rounded-[2px] bg-[#7eb0f5]" />
            <span className="absolute right-0 bottom-0 h-3.5 w-3.5 rounded-[2px] bg-[#528ff0] opacity-80" />
          </div>
          <div className="min-w-0">
            <div className="text-[13px] font-extrabold text-[var(--color-navy)] leading-tight truncate">
              Finance Control Tower
            </div>
            <div className="text-[11px] text-[var(--color-ink-muted)] font-semibold">AI Finance Controller</div>
          </div>
        </Link>
      </div>

      <nav className="flex-1 px-2.5 py-3 space-y-0.5 overflow-y-auto">
        <div className="px-2.5 pb-2 text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--color-ink-muted)]">
          Menu
        </div>
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded px-2.5 py-2 text-[13px] font-semibold transition-colors ${
                isActive
                  ? 'bg-[var(--color-rzp-soft)] text-[var(--color-rzp-dark)]'
                  : 'text-[#4a4a5a] hover:bg-[#f5f6f8] hover:text-[var(--color-navy)]'
              }`
            }
          >
            <Icon className={`h-4 w-4 shrink-0 ${'opacity-90'}`} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-3 border-t border-[var(--color-border)]">
        <div className="inline-flex items-center gap-2 rounded border border-[var(--color-border)] bg-[#fafbfc] px-2.5 py-1.5 text-[11px] font-bold text-[var(--color-navy)]">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-success)]" />
          Demo Mode
        </div>
      </div>
    </aside>
  )

  return (
    <div className="min-h-full flex bg-[var(--color-surface)]">
      <div className="hidden md:block sticky top-0 h-screen shrink-0">{sidebar}</div>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-[var(--color-navy)]/30" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 shadow-xl">{sidebar}</div>
        </div>
      )}

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-30 border-b border-[var(--color-border)] bg-white">
          <div className="px-4 sm:px-5 h-[56px] flex items-center gap-3">
            <button
              type="button"
              className="md:hidden rounded border border-[var(--color-border)] p-2"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
            >
              {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>

            <div className="min-w-0 flex-1">
              <div className="text-[14px] font-extrabold text-[var(--color-navy)] truncate">{headerMeta.title}</div>
              <div className="text-[11.5px] text-[var(--color-ink-muted)] truncate hidden sm:block font-medium">
                {headerMeta.subtitle}
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                disabled={!!busy}
                onClick={() => run('Simulation', () => api.simulation())}
                className="rzp-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 disabled:opacity-50"
              >
                <Play className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{busy === 'Simulation' ? 'Running…' : 'Run Simulation'}</span>
              </button>
              <button
                disabled={!!busy}
                onClick={() =>
                  run('Generate', () => api.generateException(), () => navigate('/exceptions'))
                }
                className="rzp-btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 disabled:opacity-50"
              >
                <Sparkles className="h-3.5 w-3.5 text-[var(--color-rzp)]" />
                <span className="hidden md:inline">Generate</span>
              </button>
              <button
                disabled={!!busy}
                onClick={() => run('Reset', () => api.resetDemo(), () => navigate('/'))}
                className="rzp-btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 disabled:opacity-50"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span className="hidden md:inline">Reset</span>
              </button>
            </div>
          </div>
        </header>

        <main className="flex-1 w-full max-w-[1180px] mx-auto px-4 sm:px-5 py-5 sm:py-6">
          <Outlet />
        </main>
      </div>

      {toast && (
        <div className="fixed bottom-5 right-5 z-50 max-w-sm rzp-card px-4 py-3 text-sm border-[#528ff0]/30">
          <div className="text-[11px] font-bold text-[var(--color-rzp)] mb-0.5">Finance Control Tower</div>
          <div className="text-[var(--color-ink)] font-medium">{toast}</div>
        </div>
      )}
    </div>
  )
}
