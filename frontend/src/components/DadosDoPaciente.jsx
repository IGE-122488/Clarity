import { useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../lib/api'
import { CONSULTAS_ALTERADAS, avisar } from '../lib/eventos'
import { descarregar, exportacaoEmTexto, mesmoNome, nomeDoFicheiro } from '../lib/exportacao'

// Passo 7 (RGPD): exportar todos os dados do paciente e apagá-lo definitivamente.
export function DadosDoPaciente({ paciente, numConsultas }) {
  const navigate = useNavigate()
  const [aExportar, setAExportar] = useState(null) // null | 'json' | 'txt'
  const [erroExportar, setErroExportar] = useState(null)
  const [confirmar, setConfirmar] = useState(false)
  const [nomeEscrito, setNomeEscrito] = useState('')
  const [aApagar, setAApagar] = useState(false)
  const [erroApagar, setErroApagar] = useState(null)

  async function exportar(formato) {
    setAExportar(formato)
    setErroExportar(null)
    try {
      const dados = await api(`/api/pacientes/${paciente.id}/exportar`)
      if (formato === 'json') {
        descarregar(JSON.stringify(dados, null, 2), nomeDoFicheiro(paciente, 'json'), 'application/json')
      } else {
        descarregar(exportacaoEmTexto(dados), nomeDoFicheiro(paciente, 'txt'), 'text/plain;charset=utf-8')
      }
    } catch (e) {
      setErroExportar(e.message)
    } finally {
      setAExportar(null)
    }
  }

  async function apagar(e) {
    e.preventDefault()
    setAApagar(true)
    setErroApagar(null)
    try {
      await api(`/api/pacientes/${paciente.id}`, {
        method: 'DELETE',
        body: JSON.stringify({ confirmacao: nomeEscrito }),
      })
      avisar(CONSULTAS_ALTERADAS) // o sino deixa de mostrar as consultas deste paciente
      navigate('/pacientes', {
        replace: true,
        state: { aviso: `${paciente.nome} e todos os dados dele(a) foram apagados definitivamente.` },
      })
    } catch (erro) {
      setErroApagar(erro.message)
      setAApagar(false)
    }
  }

  function cancelar() {
    setConfirmar(false)
    setNomeEscrito('')
    setErroApagar(null)
  }

  const consultasTexto = numConsultas === 1 ? 'a consulta' : `as ${numConsultas} consultas`

  return (
    <section className="dados-paciente" aria-labelledby="titulo-dados-paciente">
      <h2 id="titulo-dados-paciente">Dados do paciente (RGPD)</h2>

      <div className="dados-bloco">
        <h3>Exportar</h3>
        <p className="hint">
          Descarrega a ficha, todas as consultas, as notas e os briefings. Use-o quando o paciente pedir
          uma cópia dos seus dados ou antes de o apagar.
        </p>
        <div className="dados-acoes">
          <button type="button" className="botao-secundario" disabled={aExportar !== null} onClick={() => exportar('txt')}>
            {aExportar === 'txt' ? 'A preparar…' : 'Descarregar em texto (.txt)'}
          </button>
          <button type="button" className="botao-secundario" disabled={aExportar !== null} onClick={() => exportar('json')}>
            {aExportar === 'json' ? 'A preparar…' : 'Descarregar em JSON'}
          </button>
        </div>
        {erroExportar && (
          <p className="error" role="alert">
            {erroExportar}
          </p>
        )}
      </div>

      <div className="dados-bloco dados-perigo">
        <h3>Apagar definitivamente</h3>
        {!confirmar ? (
          <>
            <p className="hint">
              Apaga a ficha, {consultasTexto}, todas as notas e os briefings deste paciente. Não é possível
              desfazer. Para deixar de o ver na lista sem apagar nada, arquive-o.
            </p>
            <button type="button" className="botao-perigo" onClick={() => setConfirmar(true)}>
              Apagar paciente…
            </button>
          </>
        ) : (
          <form onSubmit={apagar}>
            <p>
              <strong>Isto não se pode desfazer.</strong> Vão ser apagados a ficha, {consultasTexto}, todas as
              notas e os briefings de <strong>{paciente.nome}</strong>. Se precisar de uma cópia, exporte primeiro.
            </p>
            <label htmlFor="confirmar-nome">
              Para confirmar, escreva o nome do paciente: <strong>{paciente.nome}</strong>
            </label>
            <input
              id="confirmar-nome"
              value={nomeEscrito}
              onChange={(e) => setNomeEscrito(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              autoFocus
            />
            <div className="dados-acoes">
              <button type="submit" className="botao-perigo" disabled={aApagar || !mesmoNome(nomeEscrito, paciente.nome)}>
                {aApagar ? 'A apagar…' : 'Apagar definitivamente'}
              </button>
              <button type="button" className="botao-secundario" disabled={aApagar} onClick={cancelar}>
                Cancelar
              </button>
            </div>
            {erroApagar && (
              <p className="error" role="alert">
                {erroApagar}
              </p>
            )}
          </form>
        )}
      </div>
    </section>
  )
}
