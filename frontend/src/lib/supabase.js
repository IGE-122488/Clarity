import { createClient } from '@supabase/supabase-js'
import { readEnv } from './env'

const env = readEnv()

// No frontend, o Supabase serve APENAS para o login (sessão do psicólogo).
// Os dados (pacientes, notas, resumos, briefings) passam sempre pela API em Python.
export const supabase = createClient(env.supabaseUrl, env.supabasePublishableKey)

export const appEnv = env.appEnv
