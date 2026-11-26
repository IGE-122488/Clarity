// Avisos entre partes da app que não estão ligadas diretamente (ex.: a agenda e o sino).
export const CONSULTAS_ALTERADAS = 'clarity:consultas-alteradas'
export const BRIEFING_AUTOMATICO = 'clarity:briefing-automatico' // detail: { consultaId, emCurso, gerado }

export function avisar(nome, detail) {
  window.dispatchEvent(new CustomEvent(nome, { detail }))
}

// Briefings que o sino está a gerar neste momento. O painel da consulta consulta esta lista ao
// abrir, para mostrar "A gerar…" mesmo que tenha sido aberto já a meio da geração.
const emCurso = new Set()

export function briefingAGerar(consultaId) {
  return emCurso.has(consultaId)
}

export function inicioDoBriefingAutomatico(consultaId) {
  emCurso.add(consultaId)
  avisar(BRIEFING_AUTOMATICO, { consultaId, emCurso: true, gerado: false })
}

export function fimDoBriefingAutomatico(consultaId, gerado) {
  emCurso.delete(consultaId)
  avisar(BRIEFING_AUTOMATICO, { consultaId, emCurso: false, gerado })
}
