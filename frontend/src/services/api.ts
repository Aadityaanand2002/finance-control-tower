const API_BASE = import.meta.env.VITE_API_URL || ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : 'Request failed')
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; demo_mode: boolean; ai_provider: string }>('/api/health'),
  dashboard: () => request<import('../types').Dashboard>('/api/dashboard'),
  exceptions: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request<import('../types').Exception[]>(`/api/exceptions${qs}`)
  },
  exceptionDetail: (id: string) => request<import('../types').ExceptionDetail>(`/api/exceptions/${id}`),
  analyze: (id: string) => request<import('../types').AIAnalysisResult>(`/api/exceptions/${id}/analyze`, { method: 'POST' }),
  review: (id: string) => request(`/api/exceptions/${id}/review`, { method: 'POST', body: '{}' }),
  approve: (id: string) => request(`/api/exceptions/${id}/approve`, { method: 'POST', body: '{}' }),
  reject: (id: string) => request(`/api/exceptions/${id}/reject`, { method: 'POST', body: '{}' }),
  resolve: (id: string) => request(`/api/exceptions/${id}/resolve`, { method: 'POST', body: '{}' }),
  financeRequest: (id: string) => request(`/api/exceptions/${id}/finance-request`, { method: 'POST', body: '{}' }),
  reconciliation: () => request<import('../types').ReconciliationMatch[]>('/api/reconciliation'),
  runReconciliation: () => request('/api/reconciliation/run', { method: 'POST' }),
  cash: () => request<import('../types').CashPosition>('/api/cash-position'),
  auditLog: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request<import('../types').AuditLog[]>(`/api/audit-log${qs}`)
  },
  aiQuery: (query: string) =>
    request<import('../types').AIQueryResponse>('/api/ai/query', {
      method: 'POST',
      body: JSON.stringify({ query }),
    }),
  simulation: () => request<{ message: string; exceptions_created: string[]; events: import('../types').ActivityEvent[] }>('/api/simulation/run', { method: 'POST' }),
  generateException: () => request<{ message: string; exceptions_created: string[] }>('/api/simulation/generate-exception', { method: 'POST' }),
  resetDemo: () => request<{ message: string; unreconciled_amount: number }>('/api/demo/reset', { method: 'POST' }),
  payments: () => request('/api/payments'),
  settlements: () => request('/api/settlements'),
}
