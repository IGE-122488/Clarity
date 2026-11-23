import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api } from '../lib/api'
import { formatarDataLonga, formatarHora } from '../lib/datas'
import { useSession } from '../lib/useSession'

// Ficha do paciente: dados e todas as consultas, com as notas de cada uma.
// Só DADOS FICTÍCIOS até haver DPIA aprovada.
const NOMES_ESTADO = {
  agendada: 'Agendada',
  realizada: 'Realizada',
  faltou: 'Faltou',
  cancelada: 'Cancelada',
}

function NotasConsulta({ consulta, onGuardado }) {
  const [notas, setNotas] = useState(consulta.notas ?? '')
  const [estado, setEstado] = useState(null) // null | 'a guardar' | 'guardado' | mensagem de erro
  const alterado = notas !== (consulta.notas ?? '')

  async function guardar() {
    setEstado('a guardar')
    try {
      const atualizada = await api(`/api/consultas/${consulta.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ notas: notas.trim() ? notas : null }),
      })
      onGuardado(atualizada)
      setEstado('guardado')
    } catch (e) {
      setEstado(e.message)
    }
  }

  return (
    <div className="notas">
      <textarea
        rows={4}
        maxLength={20000}
        value={notas}
        onChange={(e) => {
          setNotas(e.target.value)
          setEstado(null)
        }}
        placeholder="Notas da sessão (apenas dados fictícios)"
        aria-label="Notas da sessão"
      />
      <div className="notas-acoes">
        <button type="button" disabled={!alterado || estado === 'a guardar'} onClick={guardar}>
          {estado === 'a guardar' ? 'A guardar…' : 'Guardar notas'}
        </button>
        {estado === 'guardado' && <span className="ok">Guardado.</span>}
        {estado && !['a guardar', 'guardado'].includes(estado) && (
          <span className="error" role="alert">
            {estado}
          </span>
        )}
      </div>
    </div>
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
        <p className="hint">
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
    .reverse() // a API devolve as mais recentes primeiro; as próximas mostram-se pela ordem em que acontecem
  const anteriores = consultas.filter((c) => !proximas.includes(c))

  function atualizar(nova) {
    setConsultas((lista) => lista.map((c) => (c.id === nova.id ? nova : c)))
  }

  return (
    <section>
      <p className="hint">
        <Link to="/pacientes">‹ Pacientes</Link>
      </p>
      <h1>{paciente.nome}</h1>
      <p className="hint">
        {paciente.data_nascimento
          ? `Nascido(a) a ${paciente.data_nascimento.split('-').reverse().join('/')}`
          : 'Sem data de nascimento'}
        {!paciente.ativo && ' · Arquivado'} · Apenas dados fictícios.
      </p>

      <h2>Próximas consultas</h2>
      {proximas.length === 0 ? (
        <p>
          Nenhuma consulta marcada. <Link to="/agenda">Marcar na agenda</Link>
        </p>
      ) : (
        <ul className="lista-consultas">
          {proximas.map((c) => (
            <li key={c.id}>
              <strong>
                {formatarDataLonga(new Date(c.inicio))}, {formatarHora(new Date(c.inicio))}–
                {formatarHora(new Date(c.fim))}
              </strong>
            </li>
          ))}
        </ul>
      )}

      <h2>Histórico e notas</h2>
      {anteriores.length === 0 ? (
        <p>Ainda não há consultas anteriores.</p>
      ) : (
        <ul className="lista-consultas">
          {anteriores.map((c) => (
            <li key={c.id}>
              <div className="consulta-titulo">
                <strong>
                  {formatarDataLonga(new Date(c.inicio))}, {formatarHora(new Date(c.inicio))}
                </strong>
                <span className={`etiqueta estado-${c.estado}`}>{NOMES_ESTADO[c.estado]}</span>
              </div>
              <NotasConsulta consulta={c} onGuardado={atualizar} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
