import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ConsultaPainel } from '../components/ConsultaPainel'
import { api } from '../lib/api'
import {
  DIAS_SEMANA,
  formatarDia,
  formatarHora,
  inicioDaSemana,
  mesmoDia,
  minutosDesdeMeiaNoite,
  somarDias,
} from '../lib/datas'
import { CONSULTAS_ALTERADAS, avisar } from '../lib/eventos'
import { useSession } from '../lib/useSession'

// Vista semanal da agenda. Só DADOS FICTÍCIOS até haver DPIA aprovada.
const PRIMEIRA_HORA = 7
const ULTIMA_HORA = 22 // a grelha acaba às 22:00
const PX_POR_HORA = 56
const HORAS = Array.from({ length: ULTIMA_HORA - PRIMEIRA_HORA }, (_, i) => PRIMEIRA_HORA + i)
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// ?dia=2026-12-01 (dia local) ou ?dia=<data ISO com hora>, vindos dos links do sino.
function lerDia(valor) {
  if (!valor) return null
  const d = /^\d{4}-\d{2}-\d{2}$/.test(valor) ? new Date(`${valor}T12:00`) : new Date(valor)
  return Number.isNaN(d.getTime()) ? null : d
}

// Índice (0 = segunda) do dia a mostrar no telemóvel: hoje, se estiver nessa semana; senão, segunda.
function diaInicial(segunda, dia = new Date()) {
  const i = Math.round((meiaNoite(dia) - segunda) / 86400000) // round: dias de 23 h ou 25 h na mudança de hora
  return i >= 0 && i < 7 ? i : 0
}

function meiaNoite(data) {
  const d = new Date(data)
  d.setHours(0, 0, 0, 0)
  return d
}

// "23 – 29 de novembro de 2026" ou "30 de novembro – 6 de dezembro de 2026".
function intervaloLongo(primeiro, ultimo) {
  const mes = (d) => d.toLocaleDateString('pt-PT', { month: 'long' })
  const ano = ultimo.getFullYear()
  if (primeiro.getMonth() === ultimo.getMonth()) {
    return `${primeiro.getDate()} – ${ultimo.getDate()} de ${mes(ultimo)} de ${ano}`
  }
  const inicio = `${primeiro.getDate()} de ${mes(primeiro)}`
  const anoInicio = primeiro.getFullYear() === ano ? '' : ` de ${primeiro.getFullYear()}`
  return `${inicio}${anoInicio} – ${ultimo.getDate()} de ${mes(ultimo)} de ${ano}`
}

// O estado vai sempre escrito no bloco (e com ✓/✕ nos que confundem quem não distingue verde de vermelho),
// para não depender só da cor.
const ESTADOS = { agendada: 'Agendada', realizada: 'Realizada', faltou: 'Faltou', cancelada: 'Cancelada' }

function rotuloEstado(consulta) {
  if (consulta.estado_automatico) return 'Por confirmar'
  return ESTADOS[consulta.estado] ?? consulta.estado
}

function simboloEstado(consulta) {
  if (consulta.estado === 'realizada' && !consulta.estado_automatico) return '✓'
  if (consulta.estado === 'faltou') return '✕'
  return null
}

const LEGENDA = [
  ['agendada', 'Agendada'],
  ['por-confirmar', 'Por confirmar'],
  ['realizada', 'Realizada'],
  ['faltou', 'Faltou'],
  ['cancelada', 'Cancelada'],
]

function posicao(consulta) {
  const inicio = new Date(consulta.inicio)
  const fim = new Date(consulta.fim)
  const minimo = PRIMEIRA_HORA * 60
  const maximo = ULTIMA_HORA * 60
  const de = Math.min(Math.max(minutosDesdeMeiaNoite(inicio), minimo), maximo - 15)
  const ate = Math.max(Math.min(minutosDesdeMeiaNoite(fim) || 24 * 60, maximo), de + 15)
  return { top: ((de - minimo) / 60) * PX_POR_HORA, height: ((ate - de) / 60) * PX_POR_HORA }
}

function topoDaHora(data) {
  const minutos = minutosDesdeMeiaNoite(data)
  if (minutos < PRIMEIRA_HORA * 60 || minutos >= ULTIMA_HORA * 60) return null
  return ((minutos - PRIMEIRA_HORA * 60) / 60) * PX_POR_HORA
}

// Consultas que se sobrepõem no mesmo dia ficam lado a lado, em colunas, em vez de umas por cima das outras.
function dispor(consultasDoDia) {
  const ordenadas = [...consultasDoDia].sort((a, b) => new Date(a.inicio) - new Date(b.inicio))
  const resultado = []
  let grupo = []
  let fimDoGrupo = 0
  let colunasFim = []

  const fecharGrupo = () => {
    grupo.forEach((item) => resultado.push({ ...item, colunas: colunasFim.length }))
    grupo = []
    colunasFim = []
  }

  for (const consulta of ordenadas) {
    const inicio = new Date(consulta.inicio).getTime()
    const fim = new Date(consulta.fim).getTime()
    if (grupo.length > 0 && inicio >= fimDoGrupo) fecharGrupo()
    let coluna = colunasFim.findIndex((fimColuna) => fimColuna <= inicio)
    if (coluna === -1) {
      coluna = colunasFim.length
      colunasFim.push(fim)
    } else {
      colunasFim[coluna] = fim
    }
    grupo.push({ consulta, coluna })
    fimDoGrupo = grupo.length === 1 ? fim : Math.max(fimDoGrupo, fim)
  }
  fecharGrupo()
  return resultado
}

export function Agenda() {
  const session = useSession()
  const [segunda, setSegunda] = useState(() => inicioDaSemana(new Date()))
  const [indiceDia, setIndiceDia] = useState(() => diaInicial(inicioDaSemana(new Date()))) // vista de um dia no telemóvel
  const [agora, setAgora] = useState(() => new Date())
  const [consultas, setConsultas] = useState(null)
  const [pacientes, setPacientes] = useState([])
  const [erro, setErro] = useState(null)
  const [recarregar, setRecarregar] = useState(0)
  const [painel, setPainel] = useState(null) // { consultaId } ou { inicioSugerido }
  const [mostrarCanceladas, setMostrarCanceladas] = useState(false)
  const [parametros, setParametros] = useSearchParams()

  // Links do sino: /agenda?consulta=<id>&dia=<data> abre essa semana e essa consulta.
  useEffect(() => {
    const dia = lerDia(parametros.get('dia'))
    const consulta = parametros.get('consulta')
    const nova = parametros.get('nova') // "Marcar consulta" no ecrã Hoje
    if (!dia && !consulta && !nova) return
    if (dia) {
      setSegunda(inicioDaSemana(dia))
      setIndiceDia(diaInicial(inicioDaSemana(dia), dia))
    }
    if (consulta && UUID.test(consulta)) setPainel({ consultaId: consulta })
    else if (nova) setPainel({ inicioSugerido: null })
    setParametros({}, { replace: true })
  }, [parametros, setParametros])

  const dias = useMemo(() => Array.from({ length: 7 }, (_, i) => somarDias(segunda, i)), [segunda])
  const hoje = agora

  function irParaSemana(novaSegunda) {
    setSegunda(novaSegunda)
    setIndiceDia(diaInicial(novaSegunda))
  }

  // A linha da hora atual anda sozinha.
  useEffect(() => {
    const id = setInterval(() => setAgora(new Date()), 60000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (!session) return
    const de = segunda.toISOString()
    const ate = somarDias(segunda, 7).toISOString()
    api(`/api/consultas?de=${encodeURIComponent(de)}&ate=${encodeURIComponent(ate)}`)
      .then((lista) => {
        setConsultas(lista)
        setErro(null)
      })
      .catch((e) => setErro(e.message))
  }, [session, segunda, recarregar])

  // O sino passou consultas a "realizada" ou o psicólogo confirmou-as: volta a carregar a semana.
  useEffect(() => {
    const aoMudar = () => setRecarregar((n) => n + 1)
    window.addEventListener(CONSULTAS_ALTERADAS, aoMudar)
    return () => window.removeEventListener(CONSULTAS_ALTERADAS, aoMudar)
  }, [])

  useEffect(() => {
    if (!session) return
    // Inclui os arquivados só para mostrar o nome em consultas antigas.
    api('/api/pacientes?arquivados=true')
      .then(setPacientes)
      .catch((e) => setErro(e.message))
  }, [session])

  const nomes = useMemo(() => Object.fromEntries(pacientes.map((p) => [p.id, p.nome])), [pacientes])
  const nomeDoPaciente = (id) => nomes[id] ?? 'Paciente'

  if (session === undefined) return <p>A carregar…</p>
  if (!session) {
    return (
      <section>
        <h1>Agenda</h1>
        <p>
          <Link to="/entrar">Inicie sessão</Link> para ver a sua agenda.
        </p>
      </section>
    )
  }

  function guardado() {
    setPainel(null)
    avisar(CONSULTAS_ALTERADAS) // a agenda (ver acima) e o sino voltam a carregar
  }

  return (
    <section className="agenda-pagina">
      <header className="agenda-cabecalho">
        <div>
          <h1>Agenda</h1>
          <p className="agenda-intervalo">{intervaloLongo(dias[0], dias[6])}</p>
        </div>
        <div className="agenda-acoes">
          <div className="agenda-navegacao">
            <button
              type="button"
              className="botao-secundario"
              onClick={() => irParaSemana(somarDias(segunda, -7))}
              aria-label="Semana anterior"
              title="Semana anterior"
            >
              ‹
            </button>
            <button type="button" className="botao-secundario" onClick={() => irParaSemana(inicioDaSemana(new Date()))}>
              Hoje
            </button>
            <button
              type="button"
              className="botao-secundario"
              onClick={() => irParaSemana(somarDias(segunda, 7))}
              aria-label="Semana seguinte"
              title="Semana seguinte"
            >
              ›
            </button>
          </div>
          <button type="button" onClick={() => setPainel({ inicioSugerido: null })}>
            Marcar consulta
          </button>
        </div>
      </header>

      <div className="agenda-opcoes">
        <ul className="agenda-legenda" aria-label="Legenda">
          {LEGENDA.map(([classe, texto]) => (
            <li key={classe}>
              <span className={`agenda-amostra amostra-${classe}`} aria-hidden="true" />
              {texto}
            </li>
          ))}
        </ul>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={mostrarCanceladas}
            onChange={(e) => setMostrarCanceladas(e.target.checked)}
          />
          Mostrar canceladas
        </label>
      </div>
      <p className="hint agenda-dica">Apenas dados fictícios. Clique numa hora livre para marcar, ou numa consulta para a abrir.</p>

      {erro && (
        <p className="error" role="alert">
          {erro}
        </p>
      )}

      <div className="agenda-dias-tel" role="group" aria-label="Dia da semana">
        {dias.map((dia, i) => {
          const temConsultas = (consultas ?? []).some(
            (c) => mesmoDia(new Date(c.inicio), dia) && c.estado !== 'cancelada',
          )
          return (
            <button
              key={dia.toISOString()}
              type="button"
              className={`agenda-dia-chip${mesmoDia(dia, hoje) ? ' hoje' : ''}`}
              aria-pressed={i === indiceDia}
              onClick={() => setIndiceDia(i)}
            >
              <span>{DIAS_SEMANA[i]}</span>
              <strong>{dia.getDate()}</strong>
              {temConsultas && <span className="agenda-dia-ponto" aria-hidden="true" />}
            </button>
          )
        })}
      </div>

      <div className="agenda-corpo">
        <div className="agenda" aria-label="Agenda semanal">
          <div className="agenda-horas" aria-hidden="true">
            <div className="agenda-dia-titulo" />
            {HORAS.map((h) => (
              <div key={h} className="agenda-hora" style={{ height: PX_POR_HORA }}>
                {String(h).padStart(2, '0')}:00
              </div>
            ))}
          </div>

          {dias.map((dia, i) => (
            <div
              key={dia.toISOString()}
              className={`agenda-dia${i === indiceDia ? ' escolhido' : ''}${i >= 5 ? ' fim-de-semana' : ''}`}
            >
              <div className={`agenda-dia-titulo${mesmoDia(dia, hoje) ? ' hoje' : ''}`}>
                <span className="agenda-dia-semana">{DIAS_SEMANA[i]}</span>
                <span className="agenda-dia-numero">{dia.getDate()}</span>
              </div>
              <div className="agenda-coluna" style={{ height: HORAS.length * PX_POR_HORA }}>
                {HORAS.map((h) => (
                  <button
                    key={h}
                    type="button"
                    className="agenda-celula"
                    style={{ height: PX_POR_HORA }}
                    aria-label={`Marcar ${DIAS_SEMANA[i]} ${formatarDia(dia)} às ${h}:00`}
                    onClick={() => {
                      const inicio = new Date(dia)
                      inicio.setHours(h, 0, 0, 0)
                      setPainel({ inicioSugerido: inicio })
                    }}
                  />
                ))}
                {dispor(
                  (consultas ?? []).filter(
                    (c) =>
                      mesmoDia(new Date(c.inicio), dia) && (mostrarCanceladas || c.estado !== 'cancelada'),
                  ),
                ).map(({ consulta: c, coluna, colunas }) => {
                  const horas = `${formatarHora(new Date(c.inicio))}–${formatarHora(new Date(c.fim))}`
                  const rotulo = rotuloEstado(c)
                  const simbolo = simboloEstado(c)
                  return (
                    <button
                      key={c.id}
                      type="button"
                      className={`agenda-consulta estado-${c.estado}${c.estado_automatico ? ' por-confirmar' : ''}`}
                      style={{
                        ...posicao(c),
                        left: `calc(${(coluna / colunas) * 100}% + 3px)`,
                        width: `calc(${100 / colunas}% - 6px)`,
                      }}
                      aria-label={`${nomeDoPaciente(c.paciente_id)}, ${horas}, ${rotulo}`}
                      onClick={() => setPainel({ consultaId: c.id })}
                    >
                      <strong>
                        {simbolo && <b aria-hidden="true">{simbolo} </b>}
                        {nomeDoPaciente(c.paciente_id)}
                      </strong>
                      {/* Só cabe a hora de início ao lado do estado; a duração vê-se pela altura do bloco. */}
                      <span>
                        {formatarHora(new Date(c.inicio))} · <em>{rotulo}</em>
                      </span>
                    </button>
                  )
                })}
                {mesmoDia(dia, hoje) && topoDaHora(agora) !== null && (
                  <div className="agenda-agora" style={{ top: topoDaHora(agora) }} aria-hidden="true" />
                )}
              </div>
            </div>
          ))}
        </div>

        {painel && (
          <ConsultaPainel
            key={painel.consultaId ?? `nova-${painel.inicioSugerido?.toISOString()}`}
            consultaId={painel.consultaId ?? null}
            inicioSugerido={painel.inicioSugerido}
            pacientes={pacientes.filter((p) => p.ativo)}
            nomeDoPaciente={nomeDoPaciente}
            onFechar={() => setPainel(null)}
            onGuardado={guardado}
          />
        )}
      </div>
    </section>
  )
}
