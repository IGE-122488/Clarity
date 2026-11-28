// Modo claro/escuro. A escolha fica neste browser (não depende do psicólogo, vale também antes de entrar).
// Sem escolha guardada, segue o modo do sistema operativo.
const CHAVE = 'clarity:tema'
const SISTEMA_ESCURO = '(prefers-color-scheme: dark)'

export function temaGuardado() {
  try {
    const valor = globalThis.localStorage.getItem(CHAVE)
    return valor === 'claro' || valor === 'escuro' ? valor : null
  } catch {
    return null // localStorage bloqueado (modo privado): segue o sistema
  }
}

export function temaDoSistema() {
  return globalThis.matchMedia?.(SISTEMA_ESCURO).matches ? 'escuro' : 'claro'
}

export function aplicarTema(tema) {
  document.documentElement.dataset.tema = tema
}

export function guardarTema(tema) {
  try {
    globalThis.localStorage.setItem(CHAVE, tema)
  } catch {
    // Sem armazenamento: a escolha vale até fechar o separador.
  }
}

// Chamado em main.jsx antes do primeiro desenho, para a página não piscar a branco.
export function iniciarTema() {
  aplicarTema(temaGuardado() ?? temaDoSistema())
}

export { SISTEMA_ESCURO }
