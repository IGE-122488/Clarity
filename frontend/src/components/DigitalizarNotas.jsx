import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'

// Lado maior da fotografia enviada: chega para ler manuscrito e fica bem abaixo dos 4 MB do Azure.
const LADO_MAXIMO = 2400
const TAMANHO_MAXIMO = 4 * 1024 * 1024 // limite do plano gratuito do Azure (lê só 2 páginas)
const DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const ACEITES = '.jpg,.jpeg,.png,.pdf,.docx,.txt'

function extensao(nome) {
  return nome.toLowerCase().split('.').pop()
}

// Reduz e converte para JPG no próprio browser (as fotos do telemóvel têm muitas vezes 5 a 10 MB).
async function prepararImagem(ficheiro) {
  const bitmap = await createImageBitmap(ficheiro, { imageOrientation: 'from-image' })
  const escala = Math.min(1, LADO_MAXIMO / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * escala)
  canvas.height = Math.round(bitmap.height * escala)
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('Não foi possível preparar a fotografia.'))),
      'image/jpeg',
      0.85,
    ),
  )
}

// .txt: lido no próprio PC, não é enviado a lado nenhum. Aceita UTF-8 e o formato antigo do Windows.
async function lerTxt(ficheiro) {
  const bytes = await ficheiro.arrayBuffer()
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    return new TextDecoder('windows-1252').decode(bytes)
  }
}

async function lerNoAzure(conteudo, tipo) {
  const { texto } = await api('/api/ocr/notas', {
    method: 'POST',
    headers: { 'Content-Type': tipo },
    body: conteudo,
  })
  return texto
}

// Importar notas: fotografia de notas manuscritas, PDF, Word (.docx) ou TXT → texto para rever →
// acrescentar às notas. Nada fica guardado até o psicólogo guardar a consulta.
// Só DADOS FICTÍCIOS até haver DPIA.
export function DigitalizarNotas({ onAcrescentar }) {
  const input = useRef(null)
  const [aLer, setALer] = useState(false)
  const [erro, setErro] = useState(null)
  const [revisao, setRevisao] = useState(null) // { texto, nome, url (só fotografias), automatico }
  const [acrescentado, setAcrescentado] = useState(false)
  const [aArrastar, setAArrastar] = useState(false)

  // Se o ficheiro for largado fora da zona, o browser abria-o e perdiam-se as alterações não guardadas.
  useEffect(() => {
    const impedir = (e) => {
      if (e.dataTransfer?.types.includes('Files')) e.preventDefault()
    }
    window.addEventListener('dragover', impedir)
    window.addEventListener('drop', impedir)
    return () => {
      window.removeEventListener('dragover', impedir)
      window.removeEventListener('drop', impedir)
    }
  }, [])

  // Liberta a fotografia da memória do browser quando deixa de ser precisa.
  const urlFotografia = revisao?.url
  useEffect(() => () => urlFotografia && URL.revokeObjectURL(urlFotografia), [urlFotografia])

  async function lerFicheiro(ficheiro) {
    const ext = extensao(ficheiro.name)
    if (ext === 'txt') {
      return { texto: await lerTxt(ficheiro), automatico: false }
    }
    if (['jpg', 'jpeg', 'png'].includes(ext)) {
      const imagem = await prepararImagem(ficheiro)
      return { texto: await lerNoAzure(imagem, 'image/jpeg'), url: URL.createObjectURL(imagem), automatico: true }
    }
    if (ext === 'pdf' || ext === 'docx') {
      if (ficheiro.size > TAMANHO_MAXIMO) throw new Error('O ficheiro é demasiado grande (máximo 4 MB).')
      const tipo = ext === 'pdf' ? 'application/pdf' : DOCX
      return { texto: await lerNoAzure(ficheiro, tipo), automatico: true }
    }
    if (ext === 'doc') throw new Error('Os ficheiros .doc antigos não são aceites. Guarde-o como .docx ou PDF.')
    throw new Error('Escolha uma fotografia (JPG ou PNG), um PDF, um Word (.docx) ou um TXT.')
  }

  async function processar(ficheiro) {
    if (!ficheiro || aLer) return
    setErro(null)
    setAcrescentado(false)
    setALer(true)
    try {
      const lido = await lerFicheiro(ficheiro)
      if (!lido.texto.trim()) throw new Error('Não foi encontrado texto neste ficheiro.')
      setRevisao({ ...lido, texto: lido.texto.trim(), nome: ficheiro.name })
    } catch (e) {
      setErro(e.message)
    } finally {
      setALer(false)
    }
  }

  function escolher(e) {
    const ficheiro = e.target.files?.[0]
    e.target.value = '' // permite escolher o mesmo ficheiro outra vez
    processar(ficheiro)
  }

  // Arrastar um ficheiro do Explorador de Ficheiros para a zona.
  function aoArrastar(e) {
    if (!e.dataTransfer.types.includes('Files')) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
    setAArrastar(true)
  }

  function aoSair(e) {
    if (!e.currentTarget.contains(e.relatedTarget)) setAArrastar(false)
  }

  function aoLargar(e) {
    e.preventDefault()
    setAArrastar(false)
    const ficheiros = e.dataTransfer.files
    if (ficheiros.length > 1) {
      setErro('Largue um ficheiro de cada vez.')
      return
    }
    processar(ficheiros[0])
  }

  function acrescentar() {
    onAcrescentar(revisao.texto.trim())
    setRevisao(null)
    setAcrescentado(true)
  }

  return (
    <div
      className={`digitalizar${aArrastar ? ' a-arrastar' : ''}`}
      onDragEnter={aoArrastar}
      onDragOver={aoArrastar}
      onDragLeave={aoSair}
      onDrop={aoLargar}
    >
      <input ref={input} type="file" accept={ACEITES} hidden onChange={escolher} />

      {aArrastar ? (
        <p className="zona-largar">Largue o ficheiro aqui</p>
      ) : (
        !revisao &&
        (aLer ? (
          <p className="zona-largar">A ler o ficheiro…</p>
        ) : (
          <div className="zona-convite">
            <svg className="zona-icone" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 15V4m0 0L7.5 8.5M12 4l4.5 4.5M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" />
            </svg>
            <p>
              <strong>Importar notas:</strong> arraste para esta caixa uma foto, PDF, Word ou TXT
            </p>
            <button type="button" className="botao-secundario" onClick={() => input.current.click()}>
              ou escolher ficheiro…
            </button>
            <p className="hint">PDF e Word: só as 2 primeiras páginas, até 4 MB.</p>
          </div>
        ))
      )}

      {acrescentado && (
        <p className="hint" role="status">
          Texto acrescentado às notas. Não se esqueça de guardar a consulta.
        </p>
      )}

      {erro && (
        <p className="error" role="alert">
          {erro}
        </p>
      )}

      {revisao && (
        <div className="revisao-ocr">
          <p className="hint">
            <strong>{revisao.nome}</strong>
            <br />
            {revisao.automatico
              ? 'Reveja e corrija o texto antes de o acrescentar. A leitura automática pode errar, sobretudo em manuscrito e números.'
              : 'Reveja o texto antes de o acrescentar.'}
          </p>
          {revisao.url && (
            <a href={revisao.url} target="_blank" rel="noreferrer" title="Abrir a fotografia em tamanho grande">
              <img src={revisao.url} alt="Fotografia das notas manuscritas" />
            </a>
          )}
          <textarea
            rows={8}
            value={revisao.texto}
            onChange={(e) => setRevisao({ ...revisao, texto: e.target.value })}
            aria-label="Texto importado"
          />
          <div className="painel-acoes">
            <button type="button" disabled={!revisao.texto.trim()} onClick={acrescentar}>
              Acrescentar às notas
            </button>
            <button type="button" className="botao-secundario" onClick={() => setRevisao(null)}>
              Descartar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
