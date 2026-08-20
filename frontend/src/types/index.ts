export type Exception = {
  id: string
  type: string
  severity: string
  entity_id: string
  entity_type: string
  amount_affected: number
  expected_value: number
  actual_value: number
  explanation?: string | null
  root_cause?: string | null
  confidence: number
  recommended_action?: string | null
  status: string
  priority_score: number
  priority_reasons?: string[] | Record<string, unknown> | null
  pattern_info?: Record<string, unknown> | null
  evidence?: unknown[] | null
  reasoning?: unknown[] | null
  requires_human_approval: boolean
  created_at: string
  resolved_at?: string | null
  related_payment_ids?: string[] | null
  related_bank_ids?: string[] | null
}

export type Payment = {
  id: string
  order_id: string
  customer_id: string
  amount: number
  currency: string
  payment_method: string
  status: string
  fee: number
  tax: number
  created_at: string
  captured_at?: string | null
  settlement_id?: string | null
  invoice_id?: string | null
}

export type Settlement = {
  id: string
  gross_amount: number
  fee: number
  tax: number
  expected_amount: number
  settled_amount?: number | null
  settlement_date: string
  utr?: string | null
  status: string
  reconciliation_status?: string | null
  match_confidence?: number | null
  notes?: string | null
  payment_ids: string[]
}

export type BankTransaction = {
  id: string
  date: string
  description: string
  reference?: string | null
  amount: number
  type: string
  utr?: string | null
  bank: string
  settlement_id?: string | null
  reconciliation_status?: string | null
  is_duplicate: boolean
}

export type AuditLog = {
  id: string
  exception_id?: string | null
  entity_id?: string | null
  entity_type?: string | null
  action: string
  performed_by: string
  timestamp: string
  old_state?: string | null
  new_state?: string | null
  explanation?: string | null
  ai_recommendation?: string | null
  user_decision?: string | null
}

export type ActivityEvent = {
  id: string
  event_type: string
  message: string
  entity_id?: string | null
  created_at: string
}

export type Dashboard = {
  total_payments: number
  total_settled: number
  pending_settlement: number
  unreconciled_amount: number
  active_exceptions: number
  high_risk_exceptions: number
  expected_cash_position: number
  recoverable_at_risk: number
  reconciliation_percentage: number
  settlement_status_distribution: Record<string, number>
  exception_severity_distribution: Record<string, number>
  cash_position_trend: { date: string; cash: number }[]
  recent_high_priority_exceptions: Exception[]
  activity_stream: ActivityEvent[]
}

export type CashPosition = {
  available_cash: number
  expected_settlements: number
  pending_receivables: number
  upcoming_expenses: number
  outstanding_refunds: number
  at_risk_unreconciled: number
  projected_net_cash: number
  calculation_steps: string[]
  control_adjusted_label: string
}

export type ExceptionDetail = {
  exception: Exception
  payments: Payment[]
  settlement?: Settlement | null
  bank_transactions: BankTransaction[]
  audit_trail: AuditLog[]
  timeline: { at?: string; label: string; kind: string }[]
}

export type ReconciliationMatch = {
  settlement_id: string
  payment_ids: string[]
  bank_ids: string[]
  status: string
  expected_amount: number
  actual_amount: number
  difference: number
  confidence: number
  signals: string[]
  explanation: string
}

export type AIQueryResponse = {
  answer: string
  supporting_records: Record<string, unknown>[]
  calculations: string[]
  reasoning: string[]
  recommended_action?: string | null
  fallback_used: boolean
}

export type AIAnalysisResult = {
  summary: string
  severity: string
  amount_affected: number
  root_cause: string
  confidence: number
  evidence: string[]
  recommended_action: string
  reasoning: string[]
  requires_human_approval: boolean
  fallback_used: boolean
  fallback_message?: string | null
}
