// Shared display helpers. NULL (undefined metric) is visually distinct from 0.
export function fmtMetric(v, digits = 3) {
  if (v === null || v === undefined) return '—'
  return Number(v).toFixed(digits)
}

export function fmtDelta(v, digits = 3) {
  if (v === null || v === undefined) return null
  const n = Number(v)
  if (Math.abs(n) < 1e-9) return { text: '±0.000', cls: 'flat' }
  const sign = n > 0 ? '+' : ''
  return { text: sign + n.toFixed(digits), cls: n > 0 ? 'up' : 'down' }
}

export const GRADE_STYLE = {
  3: { cls: 'g3', text: '高度相关' },
  2: { cls: 'g2', text: '相关' },
  1: { cls: 'g1', text: '勉强相关' },
  0: { cls: 'g0', text: '不相关' },
}

export function gradeBadge(grade) {
  if (grade === null || grade === undefined) return { cls: 'unjudged', text: '未标注' }
  return GRADE_STYLE[grade] ?? { cls: 'unjudged', text: '未标注' }
}
