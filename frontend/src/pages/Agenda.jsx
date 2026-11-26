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

function posicao(consulta) {
  const inicio = new Date(consulta.inicio)
  const fim = new Date(consulta.fim)
  const minimo = PRIMEIRA_HORA * 60
  const maximo = ULTIMA_HORA * 60
  const de = Math.min(Math.max(minutosDesdeMeiaNoite(inicio), minimo), maximo - 15)
  const ate = Math.max(Math.min(minutosDesdeMeiaNoite(fim) || 24 * 60, maximo), de + 15)
  return { top: ((de - minimo) / 60) * PX_POR_HORA, height: ((ate - de) / 60) * PX_POR_HORA }
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
    if (!dia && !consulta) return
    if (dia) setSegunda(inicioDaSemana(dia))
    if (consulta && UUID.test(consulta)) setPainel({ consultaId: consulta })
    setParametros({}, { replace: true })
  }, [parametros, setParametros])

  const dias = useMemo(() => Array.from({ length: 7 }, (_, i) => somarDias(segunda, i)), [segunda])
  const hoje = new Date()

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
    setRecarregar((n) => n + 1)
    avisar(CONSULTAS_ALTERADAS) // o sino atualiza-se logo
  }

  return (
    <section className="agenda-pagina">
      <div className="agenda-cabecalho">
        <h1>Agenda</h1>
        <div className="agenda-navegacao">
          <button type="button" className="botao-secundario" onClick={() => setSegunda(somarDias(segunda, -7))}>
            ‹ Semana anterior
          </button>
          <button type="button" className="botao-secundario" onClick={() => setSegunda(inicioDaSemana(new Date()))}>
            Hoje
          </button>
          <button type="button" className="botao-secundario" onClick={() => setSegunda(somarDias(segunda, 7))}>
            Semana seguinte ›
          </button>
        </div>
        <span className="agenda-intervalo">
          {formatarDia(dias[0])} – {formatarDia(dias[6])}
        </span>
        <button type="button" onClick={() => setPainel({ inicioSugerido: null })}>
          + Marcar consulta
        </button>
      </div>
      <div className="agenda-opcoes">
        <p className="hint">Apenas dados fictícios. Clique numa hora livre para marcar, ou numa consulta para a abrir.</p>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={mostrarCanceladas}
            onChange={(e) => setMostrarCanceladas(e.target.checked)}
          />
          Mostrar canceladas
        </label>
      </div>

      {erro && (
        <p className="error" role="alert">
          {erro}
        </p>
      )}

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
            <div key={dia.toISOString()} className="agenda-dia">
              <div className={`agenda-dia-titulo${mesmoDia(dia, hoje) ? ' hoje' : ''}`}>
                {DIAS_SEMANA[i]} {formatarDia(dia)}
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
                ).map(
                  ({ consulta: c, coluna, colunas }) => (
                    <button
                      key={c.id}
                      type="button"
                      className={`agenda-consulta estado-${c.estado}`}
                      style={{
                        ...posicao(c),
                        left: `calc(${(coluna / colunas) * 100}% + 2px)`,
                        width: `calc(${100 / colunas}% - 4px)`,
                      }}
                      onClick={() => setPainel({ consultaId: c.id })}
                    >
                      <strong>{nomeDoPaciente(c.paciente_id)}</strong>
                      <span>
                        {formatarHora(new Date(c.inicio))}–{formatarHora(new Date(c.fim))}
                        {c.estado !== 'agendada' && ` · ${c.estado}`}
                      </span>
                    </button>
                  ),
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
