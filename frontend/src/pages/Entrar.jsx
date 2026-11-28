import { useState } from 'react'
import { useNavigate } from 'react-router'
import { supabase } from '../lib/supabase'

export function Entrar() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [erro, setErro] = useState(null)
  const [aEnviar, setAEnviar] = useState(false)

  async function submeter(e) {
    e.preventDefault()
    setErro(null)
    setAEnviar(true)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    setAEnviar(false)
    if (error) {
      setErro('Email ou palavra-passe incorretos.')
      return
    }
    navigate('/', { replace: true }) // o ecrã Hoje; "Voltar" no browser não regressa ao formulário
  }

  return (
    <section className="narrow">
      <h1>Iniciar sessão</h1>
      <form onSubmit={submeter} className="form">
        <label>
          Email
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Palavra-passe
          <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {erro && <p className="error" role="alert">{erro}</p>}
        <button type="submit" disabled={aEnviar}>{aEnviar ? 'A entrar…' : 'Entrar'}</button>
      </form>
      <p className="hint">
        Para já, as contas de teste são criadas no Supabase (Authentication → Users), com emails fictícios.
      </p>
    </section>
  )
}
