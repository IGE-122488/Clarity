import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { LogoMark } from '../components/Logo'
import { supabase } from '../lib/supabase'
import { useSession } from '../lib/useSession'

// Requisito 022: a ligação do email de recuperação traz aqui. O Supabase lê a ligação ao abrir a página
// e cria uma sessão temporária; com ela, o psicólogo escolhe a nova palavra-passe.
// Também serve para quem já tem sessão mudar a palavra-passe.
// Depois de guardar, a sessão termina (em todos os dispositivos) e volta-se a entrar com a palavra-passe nova.
const MINIMO = 8

// Erro que o Supabase põe no endereço quando a ligação expirou ou já foi usada.
function erroNaLigacao() {
  const parametros = new URLSearchParams(globalThis.location.hash.slice(1) || globalThis.location.search)
  return parametros.get('error_code') ?? parametros.get('error')
}

function mensagemDeErro(error) {
  if (error.code === 'same_password') return 'A nova palavra-passe tem de ser diferente da anterior.'
  if (error.code === 'weak_password') return 'Palavra-passe demasiado fraca. Use uma mais longa, com letras e números.'
  return 'Não foi possível guardar. Tente outra vez; se não der, peça uma nova ligação.'
}

function LigacaoInvalida() {
  return (
    <>
      <h1>Ligação inválida</h1>
      <p className="entrada-texto">
        Esta ligação expirou ou já foi usada. Cada ligação só funciona uma vez e durante pouco tempo.
      </p>
      <Link className="botao" to="/entrar?recuperar=1">
        Pedir nova ligação
      </Link>
    </>
  )
}

function Formulario({ onGuardada }) {
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [repetir, setRepetir] = useState('')
  const [estado, setEstado] = useState(null) // null | 'a guardar' | mensagem de erro

  async function guardar(e) {
    e.preventDefault()
    if (password !== repetir) {
      setEstado('As duas palavras-passe não são iguais.')
      return
    }
    setEstado('a guardar')
    const { error } = await supabase.auth.updateUser({ password })
    if (error) {
      setEstado(mensagemDeErro(error))
      return
    }
    onGuardada() // a partir daqui a sessão desaparece; a página não deve mostrar "ligação inválida"
    // "global" termina também as sessões noutros dispositivos; se falhar (sem rede), termina pelo menos esta.
    const { error: erroSair } = await supabase.auth.signOut({ scope: 'global' })
    if (erroSair) await supabase.auth.signOut({ scope: 'local' })
    navigate('/entrar', {
      replace: true,
      state: { aviso: 'Palavra-passe alterada. Entre com a nova palavra-passe.' },
    })
  }

  const erro = estado && estado !== 'a guardar'
  return (
    <>
      <h1>Nova palavra-passe</h1>
      <p className="entrada-texto">Escolha uma palavra-passe com pelo menos {MINIMO} caracteres.</p>
      <form onSubmit={guardar} className="form">
        <label>
          Nova palavra-passe
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={MINIMO}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <label>
          Repetir a nova palavra-passe
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={MINIMO}
            value={repetir}
            onChange={(e) => setRepetir(e.target.value)}
          />
        </label>
        {erro && (
          <p className="error" role="alert">
            {estado}
          </p>
        )}
        <button type="submit" disabled={estado === 'a guardar'}>
          {estado === 'a guardar' ? 'A guardar…' : 'Guardar palavra-passe'}
        </button>
      </form>
    </>
  )
}

export function NovaPalavraPasse() {
  const session = useSession()
  const [erroInicial] = useState(erroNaLigacao) // lido antes de o Supabase limpar o endereço
  const [guardada, setGuardada] = useState(false)

  let conteudo
  if (guardada) conteudo = <p className="entrada-texto">Palavra-passe guardada. A terminar a sessão…</p>
  else if (erroInicial) conteudo = <LigacaoInvalida />
  else if (session === undefined) conteudo = <p className="entrada-texto">A verificar a ligação…</p>
  else if (session) conteudo = <Formulario onGuardada={() => setGuardada(true)} />
  else conteudo = <LigacaoInvalida />

  return (
    <section className="entrada">
      <div className="entrada-cartao">
        <LogoMark size={44} />
        {conteudo}
      </div>
    </section>
  )
}
