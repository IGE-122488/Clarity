import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { LogoMark } from '../components/Logo'
import { api } from '../lib/api'
import { calcularAvisos, linkDaConsulta } from '../lib/avisos'
import { formatarDia, formatarHora, mesmoDia, somarDias } from '../lib/datas'
import { BRIEFING_AUTOMATICO, CONSULTAS_ALTERADAS } from '../lib/eventos'
import { useSession } from '../lib/useSession'

// Ecrã Hoje (passo 10): a próxima consulta em destaque, o dia em lista e o que falta confirmar.
// Só DADOS FICTÍCIOS até haver DPIA aprovada.

const ESTADO_TEXTO = { realizada: 'Realizada', faltou: 'Faltou', cancelada: 'Cancelada' }

function meiaNoite(data) {
  const d = new Date(data)
  d.setHours(0, 0, 0, 0)
  return d
}

function quantoFalta(inicio, agora) {
  const minutos = Math.round((inicio - agora) / 60000)
  if (minutos <= 0) return 'a decorrer'
  if (minutos < 60) return `daqui a ${minutos} min`
  const horas = Math.floor(minutos / 60)
  const resto = minutos % 60
  const minutosAMais = resto ? ` ${resto} min` : ''
  if (horas < 24) return `daqui a ${horas} h${minutosAMais}`
  const dias = Math.round((meiaNoite(inicio) - meiaNoite(agora)) / 86400000)
  return dias === 1 ? 'amanhã' : `daqui a ${dias} dias`
}

// Primeira linha da secção "Onde ficámos" do briefing (passo 8), para pré-visualizar.
function ondeFicamos(texto) {
  const linhas = texto.split('\n').map((l) => l.trim())
  const i = linhas.findIndex((l) => l.toLowerCase().startsWith('onde ficámos'))
  const linha = (i >= 0 ? linhas.slice(i + 1) : linhas).find((l) => l.startsWith('-'))
  return linha ? linha.replace(/^-\s*/, '') : null
}

function SemSessao() {
  return (
    <section className="boas-vindas">
      <LogoMark size={56} />
      <h1>Chegue a cada consulta a saber onde ficou.</h1>
      <p className="lead">
        A Clarity junta as notas de cada paciente e prepara um briefing curto antes de cada consulta.
      </p>
      <Link className="botao" to="/entrar">
        Iniciar sessão
      </Link>
      <p className="notice">Versão de testes: só com dados fictícios. Nunca introduzir dados de pacientes reais.</p>
    </section>
  )
}

function EstadoBriefing({ briefing, resumo }) {
  if (briefing === undefined) return <p>A verificar o briefing…</p>
  if (!briefing) {
    return <p>Ainda sem briefing. É gerado 15 min antes da consulta, ou quando o pedir ao abrir a consulta.</p>
  }
  return (
    <>
      <p className="proxima-briefing-estado">{briefing.revisto ? 'Briefing revisto' : 'Briefing pronto, por rever'}</p>
      {resumo && <p className="proxima-resumo">{resumo}</p>}
    </>
  )
}

function ProximaConsulta({ consulta, nome, agora }) {
  const [briefing, setBriefing] = useState(undefined) // undefined = a carregar; null = ainda não há

  useEffect(() => {
    let ativo = true
    api(`/api/consultas/${consulta.id}/briefing`)
      .then((b) => ativo && setBriefing(b))
      .catch(() => ativo && setBriefing(null))
    const aoGerar = (e) => {
      if (e.detail?.consultaId === consulta.id && !e.detail.emCurso && e.detail.gerado) {
        api(`/api/consultas/${consulta.id}/briefing`)
          .then((b) => ativo && setBriefing(b))
          .catch(() => {}) // fica o estado anterior; o painel da consulta mostra o erro, se houver
      }
    }
    window.addEventListener(BRIEFING_AUTOMATICO, aoGerar)
    return () => {
      ativo = false
      window.removeEventListener(BRIEFING_AUTOMATICO, aoGerar)
    }
  }, [consulta.id])

  const inicio = new Date(consulta.inicio)
  const fim = new Date(consulta.fim)
  const outroDia = !mesmoDia(inicio, agora)
  const resumo = briefing ? ondeFicamos(briefing.texto) : null

  return (
    <article className="proxima" aria-labelledby="proxima-titulo">
      <svg className="proxima-arcos" viewBox="0 0 100 100" aria-hidden="true">
        <path d="M83.88 23.53 A43 43 0 1 0 83.88 76.47" />
        <path d="M73.36 30.39 A30.5 30.5 0 1 0 73.36 69.61" />
        <path d="M62.50 37.05 A18 18 0 1 0 62.50 62.95" />
      </svg>
      <h2 id="proxima-titulo">Próxima consulta</h2>
      <p className="proxima-hora">
        {outroDia && <span className="proxima-dia">{formatarDia(inicio)}</span>}
        {formatarHora(inicio)}
      </p>
      <p className="proxima-nome">{nome}</p>
      <p className="proxima-quando">
        {quantoFalta(inicio, agora)}, até às {formatarHora(fim)}
      </p>

      <div className="proxima-briefing">
        <EstadoBriefing briefing={briefing} resumo={resumo} />
      </div>

      <div className="proxima-acoes">
        <Link className="botao botao-claro" to={linkDaConsulta(consulta)}>
          Abrir consulta
        </Link>
        <Link className="botao botao-contorno" to={`/pacientes/${consulta.paciente_id}`}>
          Ver ficha
        </Link>
      </div>
    </article>
  )
}

function Hoje() {
  const [consultas, setConsultas] = useState(null)
  const [nomes, setNomes] = useState({})
  const [erro, setErro] = useState(null)
  const [agora, setAgora] = useState(() => new Date())

  const carregar = useCallback(async () => {
    const hoje = meiaNoite(new Date())
    const de = somarDias(hoje, -30) // para as consultas por confirmar
    const ate = somarDias(hoje, 8) // para encontrar a próxima, mesmo que não seja hoje
    try {
      const [lista, pacientes] = await Promise.all([
        api(`/api/consultas?de=${encodeURIComponent(de.toISOString())}&ate=${encodeURIComponent(ate.toISOString())}`),
        api('/api/pacientes?arquivados=true'),
      ])
      setConsultas(lista)
      setNomes(Object.fromEntries(pacientes.map((p) => [p.id, p.nome])))
      setErro(null)
    } catch (e) {
      setErro(e.message)
    }
    setAgora(new Date())
  }, [])

  useEffect(() => {
    carregar()
    const relogio = setInterval(() => setAgora(new Date()), 30 * 1000)
    window.addEventListener(CONSULTAS_ALTERADAS, carregar)
    return () => {
      clearInterval(relogio)
      window.removeEventListener(CONSULTAS_ALTERADAS, carregar)
    }
  }, [carregar])

  const nome = (id) => nomes[id] ?? 'Paciente'
  const { doDia, proxima, porConfirmar } = useMemo(() => {
    if (!consultas) return { doDia: [], proxima: null, porConfirmar: [] }
    const ordenadas = [...consultas].sort((a, b) => new Date(a.inicio) - new Date(b.inicio))
    return {
      doDia: ordenadas.filter((c) => mesmoDia(new Date(c.inicio), agora) && c.estado !== 'cancelada'),
      proxima: ordenadas.find((c) => c.estado === 'agendada' && new Date(c.fim) > agora) ?? null,
      porConfirmar: calcularAvisos(consultas, agora).porConfirmar,
    }
  }, [consultas, agora])

  const titulo = agora.toLocaleDateString('pt-PT', { weekday: 'long', day: 'numeric', month: 'long' })
  // Posição da linha "agora" na lista do dia: antes da primeira consulta que ainda não acabou.
  const indiceAgora = doDia.findIndex((c) => new Date(c.fim) > agora)

  return (
    <section className="hoje">
      <header className="hoje-cabecalho">
        <div>
          <h1>Hoje</h1>
          <p className="hoje-data">{titulo}</p>
        </div>
        <div className="hoje-atalhos">
          <Link className="botao" to="/agenda?nova=1">
            Marcar consulta
          </Link>
          <Link className="botao botao-secundario" to="/pacientes?novo=1">
            Novo paciente
          </Link>
        </div>
      </header>

      {erro && (
        <p className="error" role="alert">
          Não foi possível carregar as consultas: {erro}
        </p>
      )}

      {!consultas && !erro && <p>A carregar…</p>}

      {consultas && (
        <div className="hoje-grelha">
          {proxima ? (
            <ProximaConsulta key={proxima.id} consulta={proxima} nome={nome(proxima.paciente_id)} agora={agora} />
          ) : (
            <article className="proxima proxima-vazia">
              <h2>Próxima consulta</h2>
              <p className="proxima-nome">Sem consultas marcadas nos próximos 7 dias.</p>
              <div className="proxima-acoes">
                <Link className="botao botao-claro" to="/agenda?nova=1">
                  Marcar consulta
                </Link>
              </div>
            </article>
          )}

          <section className="dia" aria-labelledby="dia-titulo">
            <h2 id="dia-titulo">O dia</h2>
            {doDia.length === 0 ? (
              <p className="hint">Sem consultas hoje.</p>
            ) : (
              <ol className="dia-lista">
                {doDia.map((c, i) => (
                  <li key={c.id} className={new Date(c.fim) <= agora ? 'dia-passada' : undefined}>
                    {i === indiceAgora && (
                      <span className="dia-agora" aria-label={`Agora, ${formatarHora(agora)}`}>
                        Agora, {formatarHora(agora)}
                      </span>
                    )}
                    <Link to={linkDaConsulta(c)} className="dia-consulta">
                      <span className="dia-hora">
                        {formatarHora(new Date(c.inicio))}–{formatarHora(new Date(c.fim))}
                      </span>
                      <span className="dia-nome">{nome(c.paciente_id)}</span>
                      {c.estado !== 'agendada' && (
                        <span className={`etiqueta estado-${c.estado}${c.estado_automatico ? ' por-confirmar' : ''}`}>
                          {c.estado_automatico ? 'Por confirmar' : ESTADO_TEXTO[c.estado]}
                        </span>
                      )}
                    </Link>
                  </li>
                ))}
                {indiceAgora === -1 && (
                  <li>
                    <span className="dia-agora">Agora, {formatarHora(agora)}</span>
                  </li>
                )}
              </ol>
            )}
          </section>

          {porConfirmar.length > 0 && (
            <section className="confirmar" aria-labelledby="confirmar-titulo">
              <h2 id="confirmar-titulo">Por confirmar</h2>
              <p className="hint">
                Passaram sozinhas a Realizada no fim da hora. Confirme no sino ou abra a consulta e escolha Faltou ou
                Cancelada se não se realizaram.
              </p>
              <ul className="confirmar-lista">
                {porConfirmar.map((c) => (
                  <li key={c.id}>
                    <Link to={linkDaConsulta(c)}>
                      {nome(c.paciente_id)}, {formatarDia(new Date(c.inicio))} às {formatarHora(new Date(c.inicio))}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </section>
  )
}

export function Inicio() {
  const session = useSession()
  if (session === undefined) return <p>A carregar…</p>
  return session ? <Hoje /> : <SemSessao />
}
