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
    const erro = new Error(mensagemDeErro(body?.detail, res.status))
    erro.status = res.status
    erro.detail = body?.detail
    throw erro
  }
  return body
}

// A API responde com texto, com {mensagem, ...} ou, nos erros de validação, com uma lista.
function mensagemDeErro(detail, status) {
  if (typeof detail === 'string') return detail
  if (detail?.mensagem) return detail.mensagem
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d) => (d.msg ?? '').replace(/^Value error, /, '')).join(' ')
  }
  return `Erro ${status} ao contactar a API.`
}
