import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import DashboardPage from '../pages/Dashboard'
import { formatINR, formatINRCompact } from '../utils/format'

vi.mock('../services/api', () => ({
  api: {
    dashboard: vi.fn(),
  },
}))

import { api } from '../services/api'

describe('format utils', () => {
  it('formats INR from paise', () => {
    expect(formatINR(4250000)).toContain('42,500')
  })
  it('formats compact lakhs', () => {
    expect(formatINRCompact(28400000)).toMatch(/2\.84L/)
  })
})

describe('Dashboard', () => {
  beforeEach(() => {
    vi.mocked(api.dashboard).mockResolvedValue({
      total_payments: 10000000,
      total_settled: 5000000,
      pending_settlement: 2000000,
      unreconciled_amount: 28400000,
      active_exceptions: 9,
      high_risk_exceptions: 5,
      expected_cash_position: 1000000,
      recoverable_at_risk: 28400000,
      reconciliation_percentage: 40,
      settlement_status_distribution: { Matched: 3, Mismatched: 4 },
      exception_severity_distribution: { critical: 2, high: 5 },
      cash_position_trend: [{ date: '2026-08-20', cash: 1000000 }],
      recent_high_priority_exceptions: [
        {
          id: 'exc_1',
          type: 'partial_settlement',
          severity: 'critical',
          entity_id: 'set_1024',
          entity_type: 'settlement',
          amount_affected: 4250000,
          expected_value: 14250000,
          actual_value: 10000000,
          confidence: 0.94,
          status: 'open',
          priority_score: 85,
          requires_human_approval: true,
          created_at: new Date().toISOString(),
          explanation: 'Partial settlement',
        },
      ],
      activity_stream: [],
    })
  })

  it('loads dashboard metrics from API', async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByText(/Unreconciled exposure/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Financial overview/i)).toBeInTheDocument()
    expect(screen.getByText(/set_1024/i)).toBeInTheDocument()
  })
})
