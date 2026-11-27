// Exportação dos dados de um paciente (RGPD): o JSON vem da API; aqui faz-se a versão em texto
// legível e o descarregamento. Nada passa por servidores de terceiros: o ficheiro é criado no browser.
import { formatarHora, paraInputData } from './datas'

const ESTADOS = { agendada: 'Agendada', realizada: 'Realizada', faltou: 'Faltou', cancelada: 'Cancelada' }

const dataCurta = (iso) => new Date(iso).toLocaleDateString('pt-PT')
const dataHora = (iso) => `${dataCurta(iso)} às ${formatarHora(new Date(iso))}`

function seccao(titulo) {
  return ['', titulo, '='.repeat(titulo.length)]
}

export function exportacaoEmTexto(dados) {
  const { paciente, consultas } = dados
  const linhas = [
    'Clarity: dados do paciente',
    `Exportado em ${dataHora(dados.exportado_em)}`,
    ...seccao('PACIENTE'),
    `Nome: ${paciente.nome}`,
    `Data de nascimento: ${paciente.data_nascimento ? paciente.data_nascimento.split('-').reverse().join('/') : 'não indicada'}`,
    `Estado: ${paciente.ativo ? 'Ativo' : 'Arquivado'}`,
    `Registado em: ${dataCurta(paciente.criado_em)}`,
    ...seccao(`CONSULTAS (${consultas.length})`),
  ]
  if (consultas.length === 0) linhas.push('Sem consultas.')
  for (const c of consultas) {
    linhas.push(
      '',
      `${dataCurta(c.inicio)}, ${formatarHora(new Date(c.inicio))}–${formatarHora(new Date(c.fim))} · ${ESTADOS[c.estado] ?? c.estado}`,
      '-'.repeat(40),
      'Notas:',
      c.notas?.trim() ? c.notas.trim() : '(sem notas)',
    )
    if (c.briefing) {
      const b = c.briefing
      linhas.push(
        '',
        `Briefing gerado por IA em ${dataHora(b.gerado_em)} (${b.revisto ? 'revisto pelo psicólogo' : 'não revisto'}):`,
        b.texto.trim(),
      )
    }
  }
  return linhas.join('\r\n') + '\r\n'
}

// "Maria Fictícia" → "maria-ficticia" (para o nome do ficheiro)
export function nomeParaFicheiro(nome) {
  const limpo = nome
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
  return limpo || 'paciente'
}

export function descarregar(conteudo, nomeFicheiro, tipo) {
  const url = URL.createObjectURL(new Blob([conteudo], { type: tipo }))
  const a = document.createElement('a')
  a.href = url
  a.download = nomeFicheiro
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function nomeDoFicheiro(paciente, extensao) {
  return `clarity-${nomeParaFicheiro(paciente.nome)}-${paraInputData(new Date())}.${extensao}`
}

// Mesma regra da API: sem ligar a maiúsculas nem a espaços a mais (os acentos contam).
export function mesmoNome(a, b) {
  const normalizar = (s) => s.normalize('NFC').replace(/\s+/g, ' ').trim().toLowerCase()
  return normalizar(a) === normalizar(b)
}
