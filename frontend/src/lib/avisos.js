// Avisos do sino, calculados a partir das consultas (sem React, para se poder testar à parte).
import { paraInputData, somarDias } from './datas'

export const MINUTOS_ANTES = 15 // aviso e briefing automático: 15 min antes da consulta
export const DIAS_PARA_TRAS = 30 // consultas passadas ainda "Agendada": só as dos últimos 30 dias

const MINUTO = 60 * 1000

function meiaNoite(data) {
  const d = new Date(data)
  d.setHours(0, 0, 0, 0)
  return d
}

// Intervalo a pedir à API: dos últimos 30 dias até ao fim de amanhã (hora local).
export function intervaloDosAvisos(agora) {
  return {
    de: somarDias(agora, -DIAS_PARA_TRAS),
    ate: somarDias(meiaNoite(agora), 2),
  }
}

// consultas: lista da API (/api/consultas). agora: Date.
export function calcularAvisos(consultas, agora) {
  const t = agora.getTime()
  const inicioDeAmanha = somarDias(meiaNoite(agora), 1)
  const fimDeAmanha = somarDias(inicioDeAmanha, 1)
  const porInicio = [...consultas].sort((a, b) => new Date(a.inicio) - new Date(b.inicio))

  const proximas = porInicio.filter((c) => {
    const falta = new Date(c.inicio).getTime() - t
    return c.estado === 'agendada' && falta > 0 && falta <= MINUTOS_ANTES * MINUTO
  })

  const amanha = porInicio.filter((c) => {
    const inicio = new Date(c.inicio)
    return c.estado !== 'cancelada' && inicio >= inicioDeAmanha && inicio < fimDeAmanha
  })

  const passadas = porInicio.filter((c) => c.estado === 'agendada' && new Date(c.fim).getTime() <= t)

  // Passaram sozinhas a "realizada" no fim da hora (passo 9): o psicólogo confirma ou corrige.
  const porConfirmar = porInicio.filter((c) => c.estado === 'realizada' && c.estado_automatico)

  // Cada aviso tem uma chave: o sino conta como "novos" os que ainda não foram vistos.
  const chaves = [
    ...proximas.map((c) => `proxima:${c.id}`),
    ...(amanha.length > 0 ? [`amanha:${paraInputData(inicioDeAmanha)}:${amanha.length}`] : []),
    // Só volta a contar como novo quando mais uma consulta passa a estar por atualizar.
    ...(passadas.length > 0 ? [`passadas:${passadas[passadas.length - 1].id}`] : []),
    ...(porConfirmar.length > 0 ? [`confirmar:${porConfirmar[porConfirmar.length - 1].id}`] : []),
  ]

  return { proximas, amanha, passadas, porConfirmar, chaves, inicioDeAmanha }
}

export function minutosAte(inicio, agora) {
  return Math.max(1, Math.ceil((new Date(inicio).getTime() - agora.getTime()) / MINUTO))
}

// Link que abre a consulta na agenda, na semana certa.
export function linkDaConsulta(consulta) {
  return `/agenda?consulta=${consulta.id}&dia=${encodeURIComponent(consulta.inicio)}`
}
