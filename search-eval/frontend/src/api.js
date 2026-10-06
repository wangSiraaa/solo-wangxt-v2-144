const base = '/api'

async function request(path, options = {}) {
  const resp = await fetch(base + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      detail = (await resp.json()).detail ?? detail
    } catch { /* non-JSON error body */ }
    const err = new Error(detail)
    err.status = resp.status
    throw err
  }
  return resp.json()
}

export const api = {
  health: () => request('/health'),
  metricPolicy: () => request('/metric-policy'),
  queries: () => request('/queries'),
  judgmentSets: () => request('/judgment-sets'),
  judgmentSet: (id) => request(`/judgment-sets/${id}`),
  experiments: () => request('/experiments'),
  experiment: (id) => request(`/experiments/${id}`),
  createExperiment: (body) =>
    request('/experiments', { method: 'POST', body: JSON.stringify(body) }),
  runExperiment: (id, role) =>
    request(`/experiments/${id}/runs/${role}`, { method: 'POST' }),
  compare: (id) => request(`/experiments/${id}/compare`),
  drilldown: (id, qid) => request(`/experiments/${id}/queries/${qid}`),
}
