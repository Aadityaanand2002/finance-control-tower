/** Format paise integer as Indian Rupee string */
export function formatINR(paise: number | null | undefined): string {
  const rupees = (paise || 0) / 100
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(rupees)
}

export function formatINRCompact(paise: number): string {
  const rupees = paise / 100
  if (Math.abs(rupees) >= 100000) {
    return `₹${(rupees / 100000).toFixed(2)}L`
  }
  if (Math.abs(rupees) >= 1000) {
    return `₹${(rupees / 1000).toFixed(1)}K`
  }
  return formatINR(paise)
}

export function severityClass(severity: string): string {
  switch (severity?.toLowerCase()) {
    case 'critical':
      return 'bg-[#fdecec] text-[#c53030] border-[#f5c6c6]'
    case 'high':
      return 'bg-[#fff1e8] text-[#c05621] border-[#f5d0b5]'
    case 'medium':
      return 'bg-[#fff8e6] text-[#976600] border-[#f0e0a8]'
    default:
      return 'bg-[#f5f6f8] text-[#4a4a5a] border-[#e6e8eb]'
  }
}

export function statusClass(status: string): string {
  const s = status?.toLowerCase() || ''
  if (s.includes('match') && !s.includes('mismatch') && !s.includes('partial'))
    return 'text-[#0f7a4c] bg-[#e8f8f0]'
  if (s.includes('critical') || s.includes('mismatch') || s.includes('missing'))
    return 'text-[#c53030] bg-[#fdecec]'
  if (s.includes('partial') || s.includes('duplicate')) return 'text-[#c05621] bg-[#fff1e8]'
  if (s.includes('approved') || s.includes('resolved')) return 'text-[#2b6de0] bg-[#eef4fe]'
  return 'text-[#4a4a5a] bg-[#f5f6f8]'
}

/** Parse API timestamps (UTC Z or IST offset) and show India local time. */
export function formatDate(iso?: string | null): string {
  if (!iso) return '—'
  const hasZone = /Z$/i.test(iso) || /[+-]\d{2}:\d{2}$/.test(iso)
  const normalized = iso.includes('T') && !hasZone ? `${iso}Z` : iso
  const d = new Date(normalized)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
