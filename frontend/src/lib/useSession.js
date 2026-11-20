import { useEffect, useState } from 'react'
import { supabase } from './supabase'

// Sessão atual do psicólogo (null se não tiver iniciado sessão).
export function useSession() {
  const [session, setSession] = useState(undefined)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s))
    return () => data.subscription.unsubscribe()
  }, [])

  return session
}
