// Pequenas ajudas para mostrar pacientes (lista e ficha).

// "Maria João Fictícia" -> "MF" (primeira e última palavra).
export function iniciais(nome) {
  const palavras = (nome ?? '').trim().split(/\s+/).filter(Boolean)
  if (palavras.length === 0) return '?'
  const primeira = palavras[0][0]
  const ultima = palavras.length > 1 ? palavras.at(-1)[0] : ''
  return (primeira + ultima).toUpperCase()
}

// Idade em anos a partir de "AAAA-MM-DD"; null se não houver data.
export function idade(dataNascimento, hoje = new Date()) {
  if (!dataNascimento) return null
  const [ano, mes, dia] = dataNascimento.split('-').map(Number)
  let anos = hoje.getFullYear() - ano
  if (hoje.getMonth() + 1 < mes || (hoje.getMonth() + 1 === mes && hoje.getDate() < dia)) anos -= 1
  return anos
}

// "AAAA-MM-DD" -> "DD/MM/AAAA"
export function formatarDataISO(iso) {
  if (!iso) return '—'
  const [ano, mes, dia] = iso.split('-')
  return `${dia}/${mes}/${ano}`
}
