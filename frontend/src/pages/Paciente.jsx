import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { DadosDoPaciente } from '../components/DadosDoPaciente'
import { api } from '../lib/api'
import { linkDaConsulta } from '../lib/avisos'
import { formatarDataLonga, formatarHora } from '../lib/datas'
import { formatarDataISO, idade, iniciais } from '../lib/pacientes'
import { useSession } from '../lib/useSession'

// Ficha do paciente: resumo, próximas consultas e o histórico em linha do tempo, com as notas de cada sessão.
// Só DADOS FICTÍCIOS até haver DPIA aprovada.
const NOMES_ESTADO = {
  agendada: 'Agendada',
  realizada: 'Realizada',
  faltou: 'Faltou',
  cancelada: 'Cancelada',
}

function nomeDoEstado(consulta) {
  return consulta.estado_automatico ? 'Por confirmar' : NOMES_ESTADO[consulta.estado]
}

// As notas aparecem como texto; só se editam depois de carregar em "Editar notas", para não se mudarem sem querer.
function NotasConsulta({ consulta, onGuardado }) {
  const original = consulta.notas ?? ''
  const [aEditar, setAEditar] = useState(false)
  const [notas, setNotas] = useState(original)
  const [estado, setEstado] = useState(null) // null | 'a guardar' | 'guardado' | mensagem de erro
  const alterado = notas !== original

  async function guardar() {
    setEstado('a guardar')
    try {
      const atualizada = await api(`/api/consultas/${consulta.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ notas: notas.trim() ? notas : null }),
      })
      onGuardado(atualizada)
      setEstado('guardado')
      setAEditar(false)
    } catch (e) {
      setEstado(e.message)
    }
  }

  function cancelar() {
    setNotas(original)
    setEstado(null)
    setAEditar(false)
  }

  const erro = estado && !['a guardar', 'guardado'].includes(estado)

  if (!aEditar) {
    return (
      <div className="notas">
        {original ? <p className="notas-texto">{original}</p> : <p className="hint">Sem notas.</p>}
        <div className="notas-acoes">
          <button type="button" className="botao-secundario botao-mini" onClick={() => setAEditar(true)}>
            {original ? 'Editar notas' : 'Escrever notas'}
          </button>
          {estado === 'guardado' && (
            <span className="ok" role="status">
              Guardado.
            </span>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="notas">
      <textarea
        rows={6}
        maxLength={20000}
        value={notas}
        onChange={(e) => {
          setNotas(e.target.value)
          setEstado(null)
        }}
        placeholder="Notas da sessão (apenas dados fictícios)"
        aria-label="Notas da sessão"
        autoFocus
      />
      <div className="notas-acoes">
        <button type="button" disabled={!alterado || estado === 'a guardar'} onClick={guardar}>
          {estado === 'a guardar' ? 'A guardar…' : 'Guardar notas'}
        </button>
        <button type="button" className="botao-secundario" disabled={estado === 'a guardar'} onClick={cancelar}>
          Cancelar
        </button>
        {erro && (
          <span className="error" role="alert">
            {estado}
          </span>
        )}
      </div>
    </div>
  )
}

function Resumo({ consultas, agora }) {
  const realizadas = consultas.filter((c) => c.estado === 'realizada' && new Date(c.inicio) <= agora)
  const faltas = consultas.filter((c) => c.estado === 'faltou').length
  const primeira = consultas.filter((c) => c.estado !== 'cancelada').at(-1) // a API devolve as mais recentes primeiro
  return (
    <dl className="ficha-resumo">
      <div>
        <dt>Sessões realizadas</dt>
        <dd>{realizadas.length}</dd>
      </div>
      <div>
        <dt>Faltas</dt>
        <dd>{faltas}</dd>
      </div>
      <div>
        <dt>Primeira consulta</dt>
        <dd>{primeira ? new Date(primeira.inicio).toLocaleDateString('pt-PT') : '—'}</dd>
      </div>
    </dl>
  )
}

function ProximasConsultas({ proximas, paciente }) {
  if (proximas.length === 0) {
    return (
      <p className="vazio">
        Nenhuma consulta marcada.
        {paciente.ativo && (
          <>
            {' '}
            <Link to={`/agenda?nova=1&paciente=${paciente.id}`}>Marcar agora</Link>
          </>
        )}
      </p>
    )
  }
  return (
    <ul className="proximas-lista">
      {proximas.map((c) => (
        <li key={c.id}>
          <Link to={linkDaConsulta(c)} className="proxima-cartao">
            <span className="proxima-cartao-dia">{formatarDataLonga(new Date(c.inicio))}</span>
            <strong>
              {formatarHora(new Date(c.inicio))}–{formatarHora(new Date(c.fim))}
            </strong>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function Historico({ anteriores, onGuardado }) {
  if (anteriores.length === 0) return <p className="vazio">Ainda não há consultas anteriores.</p>

  // "Sessão N": numeradas pela ordem em que aconteceram, só as realizadas.
  const numero = {}
  anteriores
    .filter((c) => c.estado === 'realizada')
    .toReversed()
    .forEach((c, i) => {
      numero[c.id] = i + 1
    })

  return (
    <ol className="linha-tempo">
      {anteriores.map((c) => (
        <li key={c.id} className={`estado-${c.estado}${c.estado_automatico ? ' por-confirmar' : ''}`}>
          <div className="linha-tempo-topo">
            <h3>{numero[c.id] ? `Sessão ${numero[c.id]}` : 'Consulta'}</h3>
            <span className={`etiqueta estado-${c.estado}${c.estado_automatico ? ' por-confirmar' : ''}`}>
              {nomeDoEstado(c)}
            </span>
          </div>
          <p className="linha-tempo-data">
            {formatarDataLonga(new Date(c.inicio))}, {formatarHora(new Date(c.inicio))}
          </p>
          {c.estado !== 'cancelada' && <NotasConsulta consulta={c} onGuardado={onGuardado} />}
        </li>
      ))}
    </ol>
  )
}

export function Paciente() {
  const { id } = useParams()
  const session = useSession()
  const [paciente, setPaciente] = useState(null)
  const [consultas, setConsultas] = useState(null)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    if (!session) return
    Promise.all([api(`/api/pacientes/${id}`), api(`/api/pacientes/${id}/consultas`)])
      .then(([p, c]) => {
        setPaciente(p)
        setConsultas(c)
        setErro(null)
      })
      .catch((e) => setErro(e.message))
  }, [session, id])

  if (session === undefined) return <p>A carregar…</p>
  if (!session) {
    return (
      <p>
        <Link to="/entrar">Inicie sessão</Link> para ver os seus pacientes.
      </p>
    )
  }
  if (erro) {
    return (
      <section>
        <p className="voltar">
          <Link to="/pacientes">‹ Pacientes</Link>
        </p>
        <p className="error" role="alert">
          {erro}
        </p>
      </section>
    )
  }
  if (!paciente || !consultas) return <p>A carregar…</p>

  const agora = new Date()
  const proximas = consultas
    .filter((c) => new Date(c.fim) >= agora && c.estado === 'agendada')
    .toReversed() // a API devolve as mais recentes primeiro; as próximas mostram-se pela ordem em que acontecem
  const anteriores = consultas.filter((c) => !proximas.includes(c))
  const anos = idade(paciente.data_nascimento, agora)

  function atualizar(nova) {
    setConsultas((lista) => lista.map((c) => (c.id === nova.id ? nova : c)))
  }

  return (
    <section className="ficha">
      <p className="voltar">
        <Link to="/pacientes">‹ Pacientes</Link>
      </p>

      <header className="ficha-cabecalho">
        <span className="avatar avatar-grande" aria-hidden="true">
          {iniciais(paciente.nome)}
        </span>
        <div className="ficha-titulo">
          <h1>
            {paciente.nome}
            {!paciente.ativo && <span className="etiqueta etiqueta-arquivado">Arquivado</span>}
          </h1>
          <p className="pagina-subtitulo">
            {anos === null
              ? 'Sem data de nascimento'
              : `${anos} anos · nascimento a ${formatarDataISO(paciente.data_nascimento)}`}
          </p>
        </div>
        {paciente.ativo && (
          <Link className="botao" to={`/agenda?nova=1&paciente=${paciente.id}`}>
            Marcar consulta
          </Link>
        )}
      </header>

      <Resumo consultas={consultas} agora={agora} />

      <section className="ficha-seccao" aria-labelledby="proximas-titulo">
        <h2 id="proximas-titulo">Próximas consultas</h2>
        <ProximasConsultas proximas={proximas} paciente={paciente} />
      </section>

      <section className="ficha-seccao" aria-labelledby="historico-titulo">
        <h2 id="historico-titulo">Histórico e notas</h2>
        <Historico anteriores={anteriores} onGuardado={atualizar} />
      </section>

      <DadosDoPaciente paciente={paciente} numConsultas={consultas.length} onAlterado={setPaciente} />
    </section>
  )
}
