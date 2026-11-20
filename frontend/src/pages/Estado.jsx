import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useSession } from '../lib/useSession'

export function Estado() {
  const session = useSession()
  const [estado, setEstado] = useState(null)
  const [erro, setErro] = useState(null)
  const [eu, setEu] = useState(null)

  useEffect(() => {
    api('/api/estado').then(setEstado).catch((e) => setErro(e.message))
  }, [])

  async function testarSessao() {
    setEu(null)
    try {
      setEu(await api('/api/eu'))
    } catch (e) {
      setEu({ erro: e.message })
    }
  }

  return (
    <section>
      <h1>Estado do sistema</h1>
      {erro && <p className="error">API em Python sem resposta: {erro}</p>}
      <dl className="status">
        <dt>API (Python)</dt>
        <dd>{estado ? 'a responder' : erro ? 'sem resposta' : 'a verificar…'}</dd>
        <dt>Ambiente</dt>
        <dd>{estado?.ambiente ?? '—'}</dd>
        <dt>Versão da API</dt>
        <dd>{estado?.versao ?? '—'}</dd>
        <dt>Supabase</dt>
        <dd>{estado?.supabase ?? '—'}</dd>
      </dl>

      <h2>Teste de sessão (React → Supabase Auth → API em Python)</h2>
      {session ? (
        <>
          <button type="button" onClick={testarSessao}>Testar a minha sessão na API</button>
          {eu && (
            <p className={eu.erro ? 'error' : 'ok'}>
              {eu.erro ? eu.erro : `A API reconheceu a sessão de ${eu.email}.`}
            </p>
          )}
        </>
      ) : (
        <p>Inicie sessão com uma conta de teste para fazer este teste.</p>
      )}
    </section>
  )
}
