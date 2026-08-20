import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import type { AIQueryResponse } from '../types'
import { Bot, Send } from 'lucide-react'

const SUGGESTIONS = [
  'How much money is currently unreconciled?',
  'What is our highest-priority financial exception?',
  'Why is this exception high priority?',
  'Which settlement has the largest discrepancy?',
  'Show me recurring discrepancy patterns.',
  'What is our current cash position?',
  'What should finance investigate first?',
  'What happened to settlement set_1024?',
]

export default function CopilotPage() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<{ q: string; a: AIQueryResponse }[]>([])
  const [error, setError] = useState<string | null>(null)

  async function ask(q: string) {
    const text = q.trim()
    if (!text) return
    setLoading(true)
    setError(null)
    setQuery('')
    try {
      const res = await api.aiQuery(text)
      setHistory((h) => [{ q: text, a: res }, ...h])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'AI query failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => ask(s)}
            className="rounded border border-[var(--color-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--color-navy)] hover:bg-[var(--color-rzp-soft)] hover:border-[#c5d8f8] text-left"
          >
            {s}
          </button>
        ))}
      </div>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          ask(query)
        }}
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask about exceptions, settlements, cash risk…"
          className="input-pro flex-1 !py-2.5 !px-4"
        />
        <button
          type="submit"
          disabled={loading}
          className="rzp-btn-primary inline-flex items-center gap-1.5 px-4 py-2.5 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
          {loading ? '…' : 'Ask'}
        </button>
      </form>

      {error && <p className="text-sm text-[#e34848]">{error}</p>}

      <div className="space-y-4">
        {history.map((item, idx) => (
          <article key={idx} className="rzp-card p-4">
            <div className="text-[11px] font-bold uppercase tracking-wide text-[var(--color-ink-muted)]">You asked</div>
            <p className="font-bold mt-0.5 text-[var(--color-navy)]">{item.q}</p>
            <div className="mt-3 flex gap-2 items-start">
              <div className="h-8 w-8 rounded bg-[var(--color-rzp-soft)] text-[var(--color-rzp)] grid place-items-center shrink-0">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex-1 space-y-2">
                <p className="text-sm whitespace-pre-wrap leading-relaxed">{item.a.answer}</p>
                {item.a.calculations?.length > 0 && (
                  <div className="text-xs bg-[#fafbfc] border border-[var(--color-border)] rounded p-2">
                    <div className="font-bold mb-1 text-[var(--color-navy)]">Calculations</div>
                    <ul className="list-disc pl-4">
                      {item.a.calculations.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {item.a.reasoning?.length > 0 && (
                  <div className="text-xs">
                    <div className="font-bold mb-1 text-[var(--color-navy)]">Reasoning</div>
                    <ul className="list-disc pl-4 space-y-0.5">
                      {item.a.reasoning.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {item.a.recommended_action && (
                  <p className="text-sm rounded border border-[#c5d8f8] bg-[var(--color-rzp-soft)] px-3 py-2">
                    <span className="font-bold text-[var(--color-rzp-dark)]">Recommended: </span>
                    {item.a.recommended_action}
                  </p>
                )}
                {item.a.supporting_records?.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {item.a.supporting_records.map((r, i) => {
                      const id = String(r.id || r.entity_id || '')
                      const type = String(r.type || '')
                      if (type === 'exception' && id) {
                        return (
                          <Link
                            key={i}
                            to={`/exceptions/${id}`}
                            className="rounded-md border px-2 py-1 text-xs text-[var(--color-rzp)] hover:bg-[var(--color-rzp-soft)]"
                          >
                            Exception {id}
                          </Link>
                        )
                      }
                      return (
                        <span key={i} className="rounded-md border px-2 py-1 text-xs">
                          {type} {String(r.id || r.entity_id || r.vendor || '')}
                        </span>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
