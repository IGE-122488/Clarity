import { useEffect, useState } from 'react'
import { SISTEMA_ESCURO, aplicarTema, guardarTema, temaDoSistema, temaGuardado } from '../lib/tema'

// Lua no modo claro (passa a escuro), sol no modo escuro (passa a claro).
function Lua() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11Z" />
    </svg>
  )
}

function Sol() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  )
}

export function TemaBotao() {
  const [tema, setTema] = useState(() => document.documentElement.dataset.tema ?? 'claro')

  // Enquanto não houver escolha guardada, acompanha o sistema se ele mudar (ex.: modo noturno automático).
  useEffect(() => {
    const consulta = globalThis.matchMedia?.(SISTEMA_ESCURO)
    if (!consulta) return undefined
    const aoMudar = () => {
      if (temaGuardado()) return
      const novo = temaDoSistema()
      aplicarTema(novo)
      setTema(novo)
    }
    consulta.addEventListener('change', aoMudar)
    return () => consulta.removeEventListener('change', aoMudar)
  }, [])

  function alternar() {
    const novo = tema === 'escuro' ? 'claro' : 'escuro'
    aplicarTema(novo)
    guardarTema(novo)
    setTema(novo)
  }

  const rotulo = tema === 'escuro' ? 'Mudar para modo claro' : 'Mudar para modo escuro'
  return (
    <button type="button" className="tema-botao" onClick={alternar} aria-label={rotulo} title={rotulo}>
      {tema === 'escuro' ? <Sol /> : <Lua />}
    </button>
  )
}
