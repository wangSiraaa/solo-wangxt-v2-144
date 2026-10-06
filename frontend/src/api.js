const BASE = '/api'

async function get(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json()
}

export const api = {
  policy: () => get('/policy'),
  judges: () => get('/judges'),
  judgmentSets: () => get('/judgment-sets'),
  queries: (setId = 'js-synth-v1') => get(`/queries?set_id=${setId}`),
  experiments: () => get('/experiments'),
  comparison: (id) => get(`/experiments/${id}/comparison`),
  queryDetail: (id, qid) => get(`/experiments/${id}/queries/${qid}`),
  runConfigs: () => get('/run-configs'),
  search: (body) => post('/search', body),
}
