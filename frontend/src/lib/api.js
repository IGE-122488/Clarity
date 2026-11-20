import { supabase } from './supabase'

// Chama a API em Python. Junta automaticamente o token do psicólogo, se houver sessão.
export async function api(path, options = {}) {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token

  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  const body = res.headers.get('content-type')?.includes('application/json')
    ? await res.json()
    : null

  if (!res.ok) {
    throw new Error(body?.detail ?? `Erro ${res.status} ao contactar a API.`)
  }
  return body
}
