import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api } from '../lib/api'
import { guardar, ler } from '../lib/armazenamento'
import {
  MINUTOS_ANTES,
  calcularAvisos,
  intervaloDosAvisos,
  linkDaConsulta,
  minutosAte,
} from '../lib/avisos'
import { formatarDia, formatarHora, paraInputData } from '../lib/datas'
import { CONSULTAS_ALTERADAS, fimDoBriefingAutomatico, inicioDoBriefingAutomatico } from '../lib/eventos'

// Sino de notificações (passo 6). Só funciona com a app aberta num separador: não há envio de
// emails nem tarefas no servidor (isso exigiria a chave secreta do Supabase).
// As notificações do computador nunca mostram o nome do paciente (aparecem no ecrã de bloqueio).
const ATUALIZAR_MS = 2 * 60 * 1000 // vai buscar as consultas de 2 em 2 minutos
const RELOGIO_MS = 30 * 1000 // recalcula os avisos de 30 em 30 segundos
const MAX_GUARDADOS = 200
const MAX_LISTADAS = 5

const suportaNotificacoes = () => typeof window !== 'undefined' && 'Notification' in window

function plural(n, um, varios) {
  return `${n} ${n === 1 ? um : varios}`
}

function textoDoBriefing(estado, automatico) {
  if (!estado) return automatico ? 'A preparar o briefing…' : 'A verificar o briefing…'
  switch (estado.tipo) {
    case 'a-gerar':
      return 'A gerar o briefing…'
    case 'pronto':
      return estado.revisto ? 'Briefing pronto (revisto).' : 'Briefing pronto. Reveja antes de usar.'
    case 'sem-briefing':
      return 'Ainda sem briefing. Abra a consulta para o gerar.'
    case 'sem-notas':
      return 'Sem briefing: não há sessões anteriores realizadas com notas.'
    case 'sem-ia':
      return 'A IA não está disponível de momento. Abra a consulta e tente gerar o briefing.'
    default:
      return 'Não foi possível preparar o briefing. Abra a consulta e tente de novo.'
  }
}

export function Sino({ session }) {
  const utilizador = session.user.id
  const navigate = useNavigate()
  const raiz = useRef(null)

  const [consultas, setConsultas] = useState([])
  const [nomes, setNomes] = useState({})
  const [erro, setErro] = useState(null)
  const [agora, setAgora] = useState(() => new Date())
  const [aberto, setAberto] = useState(false)
  const [briefings, setBriefings] = useState({}) // consultaId -> { tipo, revisto? }
  const [automatico, setAutomatico] = useState(() => ler(utilizador, 'briefingAutomatico', true))
  const [vistos, setVistos] = useState(() => ler(utilizador, 'avisosVistos', []))
  const [permissao, setPermissao] = useState(() => (suportaNotificacoes() ? Notification.permission : null))
  const pedidos = useRef(new Set()) // consultas cujo briefing já foi pedido nesta sessão do separador

  // Consultas dos últimos 30 dias até ao fim de amanhã, e os nomes dos pacientes.
  const carregar = useCallback(async () => {
    const { de, ate } = intervaloDosAvisos(new Date())
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
    const intervalo = setInterval(carregar, ATUALIZAR_MS)
    const relogio = setInterval(() => setAgora(new Date()), RELOGIO_MS)
    const aoVoltar = () => document.visibilityState === 'visible' && carregar()
    window.addEventListener(CONSULTAS_ALTERADAS, carregar)
    document.addEventListener('visibilitychange', aoVoltar)
    return () => {
      clearInterval(intervalo)
      clearInterval(relogio)
      window.removeEventListener(CONSULTAS_ALTERADAS, carregar)
      document.removeEventListener('visibilitychange', aoVoltar)
    }
  }, [carregar])

  const { proximas, amanha, passadas, chaves, inicioDeAmanha } = useMemo(
    () => calcularAvisos(consultas, agora),
    [consultas, agora],
  )
  const novos = chaves.filter((k) => !vistos.includes(k)).length
  const nome = (id) => nomes[id] ?? 'Paciente'

  // 15 min antes: gera o briefing se ainda não houver (nunca substitui um que já exista).
  // Com a geração automática desligada, só verifica se já há briefing.
  useEffect(() => {
    for (const c of proximas) {
      if (pedidos.current.has(c.id)) continue
      pedidos.current.add(c.id)
      const caminho = `/api/consultas/${c.id}/briefing`
      if (automatico) {
        setBriefings((b) => ({ ...b, [c.id]: { tipo: 'a-gerar' } }))
        inicioDoBriefingAutomatico(c.id)
      }
      const pedido = automatico ? api(`${caminho}?so_se_nao_existir=true`, { method: 'POST' }) : api(caminho)
      pedido
        .then((briefing) => {
          const estado = briefing ? { tipo: 'pronto', revisto: briefing.revisto } : { tipo: 'sem-briefing' }
          setBriefings((b) => ({ ...b, [c.id]: estado }))
          if (automatico) fimDoBriefingAutomatico(c.id, Boolean(briefing))
        })
        .catch((e) => {
          const tipo = e.status === 422 ? 'sem-notas' : e.status === 503 ? 'sem-ia' : 'erro'
          setBriefings((b) => ({ ...b, [c.id]: { tipo } }))
          if (automatico) fimDoBriefingAutomatico(c.id, false)
          // Erro passageiro (rede, IA ocupada): volta a tentar na próxima atualização.
          if (tipo === 'erro' || tipo === 'sem-ia') pedidos.current.delete(c.id)
        })
    }
  }, [proximas, automatico])

  // Notificação do computador, uma vez por consulta, sem o nome do paciente.
  useEffect(() => {
    if (permissao !== 'granted' || proximas.length === 0) return
    const notificadas = ler(utilizador, 'consultasNotificadas', [])
    const porNotificar = proximas.filter((c) => !notificadas.includes(c.id))
    if (porNotificar.length === 0) return
    for (const c of porNotificar) {
      try {
        const aviso = new Notification('Clarity', {
          body: `Consulta daqui a ${minutosAte(c.inicio, new Date())} min. O briefing está na app.`,
          tag: `clarity-${c.id}`,
        })
        aviso.onclick = () => {
          window.focus()
          navigate(linkDaConsulta(c))
          aviso.close()
        }
      } catch {
        // Alguns browsers (ex.: Android) só permitem notificações através de um service worker.
      }
    }
    guardar(utilizador, 'consultasNotificadas', [...notificadas, ...porNotificar.map((c) => c.id)].slice(-MAX_GUARDADOS))
  }, [proximas, permissao, utilizador, navigate])

  // Ao abrir o sino, os avisos atuais passam a "vistos".
  useEffect(() => {
    if (!aberto) return
    setVistos((atuais) => {
      const faltam = chaves.filter((k) => !atuais.includes(k))
      if (faltam.length === 0) return atuais
      const juntos = [...atuais, ...faltam].slice(-MAX_GUARDADOS)
      guardar(utilizador, 'avisosVistos', juntos)
      return juntos
    })
  }, [aberto, chaves, utilizador])

  // Fecha ao clicar fora ou com Escape.
  useEffect(() => {
    if (!aberto) return
    const fora = (e) => raiz.current && !raiz.current.contains(e.target) && setAberto(false)
    const tecla = (e) => e.key === 'Escape' && setAberto(false)
    document.addEventListener('mousedown', fora)
    document.addEventListener('keydown', tecla)
    return () => {
      document.removeEventListener('mousedown', fora)
      document.removeEventListener('keydown', tecla)
    }
  }, [aberto])

  function mudarAutomatico(ligado) {
    setAutomatico(ligado)
    guardar(utilizador, 'briefingAutomatico', ligado)
    if (ligado) {
      // Volta a pedir, desta vez para gerar, as que só tinham sido verificadas.
      for (const c of proximas) {
        if (briefings[c.id]?.tipo === 'sem-briefing') pedidos.current.delete(c.id)
      }
    }
  }

  async function pedirPermissao() {
    try {
      setPermissao(await Notification.requestPermission())
    } catch {
      setPermissao(Notification.permission)
    }
  }

  const fechar = () => setAberto(false)
  const semAvisos = proximas.length === 0 && amanha.length === 0 && passadas.length === 0

  return (
    <div className="sino" ref={raiz}>
      <button
        type="button"
        className="sino-botao"
        aria-label={novos > 0 ? `Notificações: ${plural(novos, 'nova', 'novas')}` : 'Notificações'}
        aria-expanded={aberto}
        aria-haspopup="dialog"
        onClick={() => setAberto((a) => !a)}
      >
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {novos > 0 && <span className="sino-contador">{novos > 9 ? '9+' : novos}</span>}
      </button>

      {aberto && (
        <div className="sino-painel" role="dialog" aria-label="Notificações">
          <h2>Notificações</h2>

          {erro && (
            <p className="error" role="alert">
              Não foi possível atualizar os avisos: {erro}
            </p>
          )}
          {semAvisos && !erro && <p className="hint">Sem avisos de momento.</p>}

          <ul className="sino-lista">
            {proximas.map((c) => (
              <li key={c.id} className="sino-item sino-urgente">
                <Link to={linkDaConsulta(c)} onClick={fechar}>
                  <strong>Daqui a {minutosAte(c.inicio, agora)} min:</strong> consulta com {nome(c.paciente_id)}
                </Link>
                <span className="hint">{textoDoBriefing(briefings[c.id], automatico)}</span>
              </li>
            ))}

            {amanha.length > 0 && (
              <li className="sino-item">
                <strong>Amanhã ({formatarDia(inicioDeAmanha)}): {plural(amanha.length, 'consulta', 'consultas')}</strong>
                <ul className="sino-sublista">
                  {amanha.slice(0, MAX_LISTADAS).map((c) => (
                    <li key={c.id}>
                      <Link to={linkDaConsulta(c)} onClick={fechar}>
                        {formatarHora(new Date(c.inicio))} · {nome(c.paciente_id)}
                      </Link>
                    </li>
                  ))}
                  {amanha.length > MAX_LISTADAS && (
                    <li>
                      <Link to={`/agenda?dia=${encodeURIComponent(paraInputData(inicioDeAmanha))}`} onClick={fechar}>
                        e mais {amanha.length - MAX_LISTADAS}: ver na agenda
                      </Link>
                    </li>
                  )}
                </ul>
              </li>
            )}

            {passadas.length > 0 && (
              <li className="sino-item">
                <strong>
                  {passadas.length === 1
                    ? '1 consulta passada ainda está como Agendada'
                    : `${passadas.length} consultas passadas ainda estão como Agendada`}
                </strong>
                <span className="hint">
                  Marque-as como Realizada, Faltou ou Cancelada. Só as realizadas entram no briefing.
                </span>
                <ul className="sino-sublista">
                  {passadas.slice(0, MAX_LISTADAS).map((c) => (
                    <li key={c.id}>
                      <Link to={linkDaConsulta(c)} onClick={fechar}>
                        {nome(c.paciente_id)} · {formatarDia(new Date(c.inicio))} às {formatarHora(new Date(c.inicio))}
                      </Link>
                    </li>
                  ))}
                  {passadas.length > MAX_LISTADAS && (
                    <li className="hint">e mais {passadas.length - MAX_LISTADAS}</li>
                  )}
                </ul>
              </li>
            )}
          </ul>

          <div className="sino-opcoes">
            <label className="checkbox">
              <input type="checkbox" checked={automatico} onChange={(e) => mudarAutomatico(e.target.checked)} />
              Gerar o briefing automaticamente {MINUTOS_ANTES} min antes
            </label>
            {permissao === 'default' && (
              <button type="button" className="link-button" onClick={pedirPermissao}>
                Avisar também com notificações do computador (sem o nome do paciente)
              </button>
            )}
            {permissao === 'denied' && (
              <p className="hint">As notificações do computador estão bloqueadas neste browser.</p>
            )}
            <p className="hint">Os avisos só aparecem com a Clarity aberta num separador.</p>
          </div>
        </div>
      )}
    </div>
  )
}
