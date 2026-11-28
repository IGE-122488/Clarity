import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router'
import { api } from '../lib/api'
import { DIAS_SEMANA, formatarDia, formatarHora, somarDias } from '../lib/datas'
import { idade, iniciais } from '../lib/pacientes'
import { useSession } from '../lib/useSession'

// Lista e criação de pacientes. Só DADOS FICTÍCIOS até haver DPIA aprovada.
// Quem garante que cada psicólogo só vê os seus é a base de dados (RLS), não esta página.

// A API aceita no máximo 62 dias por pedido: 31 para trás (última sessão) e 31 para a frente (próxima).
const DIAS_PARA_TRAS = 31
const DIAS_PARA_A_FRENTE = 31

// Sem acentos e em minúsculas, para "joao" encontrar "João".
function normalizar(texto) {
  return texto.normalize('NFD').replaceAll(/[̀-ͯ]/g, '').toLowerCase()
}

// Por paciente: a próxima consulta marcada e a última sessão realizada, dentro da janela acima.
function resumirConsultas(consultas, agora) {
  const resumo = {}
  for (const c of consultas) {
    const r = (resumo[c.paciente_id] ??= { proxima: null, ultima: null })
    const inicio = new Date(c.inicio)
    if (c.estado === 'agendada' && new Date(c.fim) > agora) {
      if (!r.proxima || inicio < new Date(r.proxima.inicio)) r.proxima = c
    } else if (c.estado === 'realizada' && inicio <= agora && (!r.ultima || inicio > new Date(r.ultima.inicio))) {
      r.ultima = c
    }
  }
  return resumo
}

function quando(consulta) {
  const inicio = new Date(consulta.inicio)
  const dia = DIAS_SEMANA[(inicio.getDay() + 6) % 7] // getDay(): 0 = domingo
  return `${dia}, ${formatarDia(inicio)} · ${formatarHora(inicio)}`
}

function NovoPaciente({ onCriado, onFechar }) {
  const [nome, setNome] = useState('')
  const [dataNascimento, setDataNascimento] = useState('')
  const [aGuardar, setAGuardar] = useState(false)
  const [erro, setErro] = useState(null)

  async function criar(e) {
    e.preventDefault()
    setErro(null)
    setAGuardar(true)
    try {
      await api('/api/pacientes', {
        method: 'POST',
        body: JSON.stringify({ nome, data_nascimento: dataNascimento || null }),
      })
      setNome('')
      setDataNascimento('')
      onCriado()
    } catch (err) {
      setErro(err.message)
    } finally {
      setAGuardar(false)
    }
  }

  return (
    <form onSubmit={criar} className="form novo-paciente" aria-label="Novo paciente">
      <div className="novo-paciente-campos">
        <label>
          Nome
          <input required maxLength={120} value={nome} onChange={(e) => setNome(e.target.value)} autoFocus />
        </label>
        <label>
          <span>
            Data de nascimento <span className="opcional">(opcional)</span>
          </span>
          <input
            type="date"
            min="1900-01-01"
            value={dataNascimento}
            onChange={(e) => setDataNascimento(e.target.value)}
          />
        </label>
      </div>
      <p className="hint">Apenas dados fictícios. Nunca introduzir dados de pacientes reais.</p>
      <div className="painel-acoes">
        <button type="submit" disabled={aGuardar}>
          {aGuardar ? 'A guardar…' : 'Adicionar paciente'}
        </button>
        <button type="button" className="botao-secundario" onClick={onFechar}>
          Cancelar
        </button>
      </div>
      {erro && (
        <p className="error" role="alert">
          {erro}
        </p>
      )}
    </form>
  )
}

function LinhaPaciente({ paciente, resumo, agora, onArquivar }) {
  const anos = idade(paciente.data_nascimento, agora)
  return (
    <li className={`paciente-linha${paciente.ativo ? '' : ' arquivado'}`}>
      <Link to={`/pacientes/${paciente.id}`} className="paciente-ligacao">
        <span className="avatar" aria-hidden="true">
          {iniciais(paciente.nome)}
        </span>
        <span className="paciente-nome">
          <strong>{paciente.nome}</strong>
          <span>
            {anos === null ? 'Sem data de nascimento' : `${anos} anos`}
            {!paciente.ativo && ' · Arquivado'}
          </span>
        </span>
        <span className="paciente-dado">
          <small>Próxima consulta</small>
          {resumo?.proxima ? quando(resumo.proxima) : '—'}
        </span>
        <span className="paciente-dado">
          <small>Última sessão</small>
          {resumo?.ultima ? formatarDia(new Date(resumo.ultima.inicio)) : '—'}
        </span>
      </Link>
      <button
        type="button"
        className="link-button paciente-arquivar"
        onClick={() => onArquivar(paciente)}
        aria-label={`${paciente.ativo ? 'Arquivar' : 'Reativar'} ${paciente.nome}`}
      >
        {paciente.ativo ? 'Arquivar' : 'Reativar'}
      </button>
    </li>
  )
}

function ListaPacientes({ pacientes, erro, procura, resumo, agora, onArquivar }) {
  if (pacientes === null) return erro ? null : <p>A carregar…</p>
  if (pacientes.length === 0) return <p className="vazio">Ainda não tem pacientes. Comece por adicionar um.</p>
  const filtro = normalizar(procura.trim())
  const visiveis = filtro ? pacientes.filter((p) => normalizar(p.nome).includes(filtro)) : pacientes
  if (visiveis.length === 0) return <p className="vazio">Nenhum paciente com “{procura.trim()}”.</p>
  return (
    <ul className="pacientes-lista">
      {visiveis.map((p) => (
        <LinhaPaciente key={p.id} paciente={p} resumo={resumo[p.id]} agora={agora} onArquivar={onArquivar} />
      ))}
    </ul>
  )
}

export function Pacientes() {
  const session = useSession()
  const [pacientes, setPacientes] = useState(null)
  const [consultas, setConsultas] = useState([])
  const [verArquivados, setVerArquivados] = useState(false)
  const [recarregar, setRecarregar] = useState(0)
  const [erro, setErro] = useState(null)
  const [procura, setProcura] = useState('')
  const [parametros, setParametros] = useSearchParams()
  const [novoAberto, setNovoAberto] = useState(() => parametros.get('novo') === '1') // "Novo paciente" no ecrã Hoje
  const aviso = useLocation().state?.aviso // ex.: depois de apagar um paciente (passo 7)
  const agora = useMemo(() => new Date(), [])

  useEffect(() => {
    if (parametros.get('novo')) setParametros({}, { replace: true })
  }, [parametros, setParametros])

  useEffect(() => {
    if (!session) return
    api(`/api/pacientes${verArquivados ? '?arquivados=true' : ''}`)
      .then((lista) => {
        setPacientes(lista)
        setErro(null)
      })
      .catch((e) => setErro(e.message))
  }, [session, verArquivados, recarregar])

  // Só para mostrar a próxima consulta e a última sessão; se falhar, a lista continua a funcionar.
  useEffect(() => {
    if (!session) return
    const de = somarDias(agora, -DIAS_PARA_TRAS).toISOString()
    const ate = somarDias(agora, DIAS_PARA_A_FRENTE).toISOString()
    api(`/api/consultas?de=${encodeURIComponent(de)}&ate=${encodeURIComponent(ate)}`)
      .then(setConsultas)
      .catch(() => setConsultas([]))
  }, [session, agora, recarregar])

  const resumo = useMemo(() => resumirConsultas(consultas, agora), [consultas, agora])

  async function mudarArquivo(paciente) {
    setErro(null)
    try {
      await api(`/api/pacientes/${paciente.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ ativo: !paciente.ativo }),
      })
      setRecarregar((n) => n + 1)
    } catch (err) {
      setErro(err.message)
    }
  }

  if (session === undefined) return <p>A carregar…</p>
  if (!session) {
    return (
      <section>
        <h1>Pacientes</h1>
        <p>
          <Link to="/entrar">Inicie sessão</Link> para ver os seus pacientes.
        </p>
      </section>
    )
  }

  const ativos = pacientes?.filter((p) => p.ativo).length ?? 0

  return (
    <section>
      <header className="pagina-cabecalho">
        <div>
          <h1>Pacientes</h1>
          {pacientes && (
            <p className="pagina-subtitulo">
              {ativos === 1 ? '1 paciente ativo' : `${ativos} pacientes ativos`}
            </p>
          )}
        </div>
        {!novoAberto && (
          <button type="button" onClick={() => setNovoAberto(true)}>
            Novo paciente
          </button>
        )}
      </header>

      {aviso && (
        <p className="ok" role="status">
          {aviso}
        </p>
      )}

      {novoAberto && (
        <NovoPaciente
          onCriado={() => {
            setNovoAberto(false)
            setRecarregar((n) => n + 1)
          }}
          onFechar={() => setNovoAberto(false)}
        />
      )}

      {erro && (
        <p className="error" role="alert">
          {erro}
        </p>
      )}

      <div className="pacientes-filtros">
        <input
          type="search"
          className="procura"
          placeholder="Procurar por nome"
          aria-label="Procurar paciente por nome"
          value={procura}
          onChange={(e) => setProcura(e.target.value)}
        />
        <label className="checkbox">
          <input type="checkbox" checked={verArquivados} onChange={(e) => setVerArquivados(e.target.checked)} />
          Mostrar arquivados
        </label>
      </div>

      <ListaPacientes
        pacientes={pacientes}
        erro={erro}
        procura={procura}
        resumo={resumo}
        agora={agora}
        onArquivar={mudarArquivo}
      />
    </section>
  )
}
