import { useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router'
import { LogoMark } from '../components/Logo'
import { supabase } from '../lib/supabase'
import { useSession } from '../lib/useSession'

// Página de entrada e pedido de nova palavra-passe (requisito 022).
// O email de recuperação leva a /nova-palavra-passe, onde se escolhe a nova.

function mensagemDeErroAoPedir(error) {
  if (error.status === 429) return 'Já foram pedidas várias ligações. Espere um pouco e tente outra vez.'
  return 'Não foi possível enviar o email agora. Tente outra vez daqui a pouco.'
}

function PedirLigacao({ emailInicial, onVoltar }) {
  const [email, setEmail] = useState(emailInicial)
  const [estado, setEstado] = useState(null) // null | 'a enviar' | 'enviado' | mensagem de erro

  async function pedir(e) {
    e.preventDefault()
    setEstado('a enviar')
    const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${globalThis.location.origin}/nova-palavra-passe`,
    })
    setEstado(error ? mensagemDeErroAoPedir(error) : 'enviado')
  }

  if (estado === 'enviado') {
    return (
      <>
        <h1>Veja o seu email</h1>
        {/* A mesma resposta exista ou não a conta, para não revelar que emails estão registados. */}
        <p className="entrada-texto">
          Se existir uma conta com <strong>{email.trim()}</strong>, vai receber uma ligação para escolher uma nova
          palavra-passe. A ligação só pode ser usada uma vez.
        </p>
        <p className="hint">Não chegou? Veja a pasta de spam ou peça outra daqui a um minuto.</p>
        <button type="button" className="botao-secundario" onClick={onVoltar}>
          Voltar a iniciar sessão
        </button>
      </>
    )
  }

  const erro = estado && estado !== 'a enviar'
  return (
    <>
      <h1>Recuperar palavra-passe</h1>
      <p className="entrada-texto">Escreva o email da sua conta. Enviamos uma ligação para escolher uma nova.</p>
      <form onSubmit={pedir} className="form">
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        {erro && (
          <p className="error" role="alert">
            {estado}
          </p>
        )}
        <button type="submit" disabled={estado === 'a enviar'}>
          {estado === 'a enviar' ? 'A enviar…' : 'Enviar ligação'}
        </button>
      </form>
      <button type="button" className="link-button entrada-ligacao" onClick={onVoltar}>
        ‹ Voltar a iniciar sessão
      </button>
    </>
  )
}

export function Entrar() {
  const navigate = useNavigate()
  const session = useSession()
  const [parametros] = useSearchParams()
  const aviso = useLocation().state?.aviso // ex.: depois de mudar a palavra-passe
  const [modo, setModo] = useState(() => (parametros.get('recuperar') ? 'recuperar' : 'entrar'))
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [erro, setErro] = useState(null)
  const [aEnviar, setAEnviar] = useState(false)

  useEffect(() => {
    document.title = 'Entrar · Clarity'
    return () => {
      document.title = 'Clarity'
    }
  }, [])

  // Quem já tem sessão não precisa desta página.
  if (session) return <Navigate to="/" replace />

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
    <section className="entrada">
      <div className="entrada-cartao">
        <LogoMark size={44} />
        {modo === 'recuperar' ? (
          <PedirLigacao emailInicial={email} onVoltar={() => setModo('entrar')} />
        ) : (
          <>
            <h1>Iniciar sessão</h1>
            {aviso ? (
              <p className="ok" role="status">
                {aviso}
              </p>
            ) : (
              <p className="entrada-texto">Entre com o email e a palavra-passe da sua conta Clarity.</p>
            )}
            <form onSubmit={submeter} className="form">
              <label>
                Email
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              <label>
                Palavra-passe
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              {erro && (
                <p className="error" role="alert">
                  {erro}
                </p>
              )}
              <button type="submit" disabled={aEnviar}>
                {aEnviar ? 'A entrar…' : 'Entrar'}
              </button>
            </form>
            <button
              type="button"
              className="link-button entrada-ligacao"
              onClick={() => {
                setErro(null)
                setModo('recuperar')
              }}
            >
              Esqueci-me da palavra-passe
            </button>
          </>
        )}
      </div>
      <p className="hint entrada-aviso">Versão de testes: só dados fictícios.</p>
    </section>
  )
}
