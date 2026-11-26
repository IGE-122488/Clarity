// Preferências e avisos já vistos, guardados neste browser (localStorage), por psicólogo.
// Nunca guardar aqui dados de pacientes: só ids de consultas e preferências.
// O localStorage pode não existir ou estar bloqueado (modo privado): nesse caso não guarda nada.

function chave(utilizadorId, nome) {
  return `clarity:${utilizadorId}:${nome}`
}

export function ler(utilizadorId, nome, omissao) {
  try {
    const valor = window.localStorage.getItem(chave(utilizadorId, nome))
    return valor === null ? omissao : JSON.parse(valor)
  } catch {
    return omissao
  }
}

export function guardar(utilizadorId, nome, valor) {
  try {
    window.localStorage.setItem(chave(utilizadorId, nome), JSON.stringify(valor))
  } catch {
    // Sem armazenamento: a preferência vale só até fechar o separador.
  }
}
