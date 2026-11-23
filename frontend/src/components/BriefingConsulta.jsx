import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { formatarDia, formatarHora } from '../lib/datas'

// Briefing pré-sessão gerado por IA a partir das notas das sessões anteriores do paciente.
// O psicólogo pode editar o texto e marcá-lo como revisto. Só DADOS FICTÍCIOS até haver DPIA.
export function BriefingConsulta({ consultaId }) {
  const [briefing, setBriefing] = useState(undefined) // undefined = a carregar; null = ainda não há
  const [texto, setTexto] = useState('')
  const [aTrabalhar, setATrabalhar] = useState(null) // 'gerar' | 'guardar' | null
  const [erro, setErro] = useState(null)

  const caminho = `/api/consultas/${consultaId}/briefing`

  useEffect(() => {
    let ativo = true
    api(caminho)
      .then((b) => {
        if (!ativo) return
        setBriefing(b)
        setTexto(b?.texto ?? '')
      })
      .catch((e) => ativo && setErro(e.message))
    return () => {
      ativo = false
    }
  }, [caminho])

  async function pedir(acao, opcoes) {
    setErro(null)
    setATrabalhar(acao)
    try {
      const b = await api(caminho, opcoes)
      setBriefing(b)
      setTexto(b.texto)
    } catch (e) {
      setErro(e.message)
    } finally {
      setATrabalhar(null)
    }
  }

  function gerar() {
    if (briefing && !window.confirm('Gerar de novo substitui o texto atual, incluindo as suas edições. Continuar?')) {
      return
    }
    pedir('gerar', { method: 'POST' })
  }

  function guardar(marcarRevisto) {
    const corpo = {}
    if (texto !== briefing.texto) corpo.texto = texto
    if (marcarRevisto) corpo.revisto = true
    pedir('guardar', { method: 'PATCH', body: JSON.stringify(corpo) })
  }

  const editado = briefing && texto !== briefing.texto
  const ocupado = aTrabalhar !== null

  return (
    <section className="briefing" aria-label="Briefing pré-sessão">
      <div className="briefing-topo">
        <h3>Briefing pré-sessão</h3>
        {briefing && (
          <span className={`etiqueta ${briefing.revisto ? '' : 'estado-por-rever'}`}>
            {briefing.revisto ? 'Revisto' : 'Por rever'}
          </span>
        )}
      </div>

      {briefing === undefined && !erro && <p className="hint">A carregar…</p>}

      {briefing === null && (
        <p className="hint">
          Resumo das notas das últimas sessões deste paciente, feito por IA. Só entram as sessões anteriores
          marcadas como <strong>Realizada</strong> e com notas. Reveja sempre antes de usar.
        </p>
      )}

      {briefing && (
        <>
          <textarea
            rows={12}
            maxLength={20000}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            aria-label="Texto do briefing"
          />
          <p className="hint">
            Gerado por IA em {formatarDia(new Date(briefing.gerado_em))} às{' '}
            {formatarHora(new Date(briefing.gerado_em))}, a partir de {briefing.sessoes_usadas}{' '}
            {briefing.sessoes_usadas === 1 ? 'sessão realizada' : 'sessões realizadas'}. A IA pode errar:
            confirme nas notas.
          </p>
        </>
      )}

      {erro && (
        <p className="error" role="alert">
          {erro}
        </p>
      )}

      {briefing !== undefined && (
        <div className="painel-acoes">
          {briefing && (
            <>
              <button type="button" disabled={ocupado || !editado || !texto.trim()} onClick={() => guardar(false)}>
                {aTrabalhar === 'guardar' ? 'A guardar…' : 'Guardar alterações'}
              </button>
              {!briefing.revisto && (
                <button type="button" disabled={ocupado || !texto.trim()} onClick={() => guardar(true)}>
                  Marcar como revisto
                </button>
              )}
            </>
          )}
          <button
            type="button"
            className={briefing ? 'botao-secundario' : undefined}
            disabled={ocupado}
            onClick={gerar}
          >
            {aTrabalhar === 'gerar' ? 'A gerar… (pode demorar 30 s)' : briefing ? 'Gerar de novo' : 'Gerar briefing'}
          </button>
        </div>
      )}
    </section>
  )
}
