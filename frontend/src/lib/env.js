// Lê e valida as variáveis de ambiente públicas (VITE_*). Falha cedo com uma mensagem clara.
const APP_ENVS = ['development', 'preview', 'production']

function str(value) {
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : undefined
}

export function readEnv(source = import.meta.env) {
  const supabaseUrl = str(source.VITE_SUPABASE_URL)
  const supabasePublishableKey = str(source.VITE_SUPABASE_PUBLISHABLE_KEY)
  const appEnv = str(source.VITE_APP_ENV) ?? 'development'

  const missing = []
  if (!supabaseUrl) missing.push('VITE_SUPABASE_URL')
  if (!supabasePublishableKey) missing.push('VITE_SUPABASE_PUBLISHABLE_KEY')
  if (missing.length > 0) {
    throw new Error(
      `Faltam variáveis de ambiente: ${missing.join(', ')}. Copiem .env.example para .env.local e preencham-nas.`,
    )
  }
  if (!APP_ENVS.includes(appEnv)) {
    throw new Error(`VITE_APP_ENV inválido: "${appEnv}". Use development, preview ou production.`)
  }
  // A secret key / service_role nunca pode chegar ao browser.
  if (supabasePublishableKey.startsWith('sb_secret_') || supabasePublishableKey.includes('service_role')) {
    throw new Error('VITE_SUPABASE_PUBLISHABLE_KEY parece ser uma chave secreta. Usem a chave publishable.')
  }
  return { supabaseUrl, supabasePublishableKey, appEnv }
}
