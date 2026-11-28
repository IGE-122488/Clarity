import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../lib/api'
import { BriefingConsulta } from './BriefingConsulta'
import { DigitalizarNotas } from './DigitalizarNotas'
import { deInputs, formatarHora, paraInputData, paraInputHora } from '../lib/datas'

const DURACOES = [30, 45, 50, 60, 90, 120]
const ESTADOS = [
  { valor: 'agendada', nome: 'Agendada' },
  { valor: 'realizada', nome: 'Realizada' },
  { valor: 'faltou', nome: 'Faltou' },
  { valor: 'cancelada', nome: 'Cancelada' },
]

// Painel para marcar uma consulta nova (consultaId = null) ou ver/editar uma existente.
// Só DADOS FICTÍCIOS até haver DPIA aprovada.
export function ConsultaPainel({
  consultaId,
  inicioSugerido,
  pacienteInicial,
  pacientes,
  nomeDoPaciente,
  onFechar,
  onGuardado,
}) {
  const nova = !consultaId
  const [carregada, setCarregada] = useState(nova)
  const [pacienteId, setPacienteId] = useState(pacienteInicial ?? '')
  const [data, setData] = useState(paraInputData(inicioSugerido ?? new Date()))
  const [hora, setHora] = useState(paraInputHora(inicioSugerido ?? new Date()))
  const [duracao, setDuracao] = useState(50)
  const [estado, setEstado] = useState('agendada')
  const [automatico, setAutomatico] = useState(false) // passou sozinha a "realizada"; falta confirmar
  const [notas, setNotas] = useState('')
  const [erro, setErro] = useState(null)
  const [sobrepostas, setSobrepostas] = useState(null)
  const [aGuardar, setAGuardar] = useState(false)
  const [original, setOriginal] = useState(null) // horário guardado, para só remarcar se mudou

  // Esc fecha o painel, como qualquer janela por cima da página.
  useEffect(() => {
    const aoTecla = (e) => {
      if (e.key === 'Escape') onFechar()
    }
    globalThis.addEventListener('keydown', aoTecla)
    return () => globalThis.removeEventListener('keydown', aoTecla)
  }, [onFechar])

  useEffect(() => {
    if (nova) return
    api(`/api/consultas/${consultaId}`)
      .then((c) => {
        const inicio = new Date(c.inicio)
        const fim = new Date(c.fim)
        setPacienteId(c.paciente_id)
        setData(paraInputData(inicio))
        setHora(paraInputHora(inicio))
        setDuracao(Math.round((fim - inicio) / 60000))
        setOriginal(`${paraInputData(inicio)} ${paraInputHora(inicio)} ${Math.round((fim - inicio) / 60000)}`)
        setEstado(c.estado)
        setAutomatico(Boolean(c.estado_automatico))
        setNotas(c.notas ?? '')
        setCarregada(true)
      })
      .catch((e) => setErro(e.message))
  }, [consultaId, nova])

  const mudouHorario = nova || original !== `${data} ${hora} ${duracao}`

  async function enviar(corpo) {
    setErro(null)
    setAGuardar(true)
    try {
      if (nova) {
        await api('/api/consultas', {
          method: 'POST',
          body: JSON.stringify({ ...corpo, paciente_id: pacienteId }),
        })
      } else {
        await api(`/api/consultas/${consultaId}`, { method: 'PATCH', body: JSON.stringify(corpo) })
      }
      onGuardado()
    } catch (e) {
      if (e.status === 409 && e.detail?.sobrepostas) {
        setSobrepostas(e.detail.sobrepostas)
      } else {
        setErro(e.message)
      }
    } finally {
      setAGuardar(false)
    }
  }

  // Guardar ou remarcar: envia o horário só se mudou, para não voltar a verificar sobreposições.
  function guardar(ignorarSobreposicao = false) {
    const inicio = deInputs(data, hora)
    const fim = new Date(inicio.getTime() + duracao * 60000)
    return enviar({
      ...(mudouHorario ? { inicio: inicio.toISOString(), fim: fim.toISOString() } : {}),
      estado,
      notas: notas.trim() ? notas : null,
      ignorar_sobreposicao: ignorarSobreposicao,
    })
  }

  // Cancelar muda só o estado: alterações ao horário ou às notas que não foram guardadas são descartadas.
  function cancelarConsulta() {
    setSobrepostas(null)
    return enviar({ estado: 'cancelada' })
  }

  function submeter(e) {
    e.preventDefault()
    setSobrepostas(null)
    guardar()
  }

  return (
    <aside className="painel" aria-label={nova ? 'Marcar consulta' : 'Consulta'}>
      <div className="painel-topo">
        <h2>{nova ? 'Marcar consulta' : nomeDoPaciente(pacienteId) || 'Consulta'}</h2>
        <button type="button" className="link-button painel-fechar" onClick={onFechar} aria-label="Fechar" title="Fechar (Esc)">
          ✕
        </button>
      </div>

      {!nova && carregada && estado !== 'cancelada' && <BriefingConsulta key={consultaId} consultaId={consultaId} />}

      {!carregada ? (
        !erro && <p>A carregar…</p>
      ) : (
        <form onSubmit={submeter} className="form">
          {nova ? (
            <label>
              Paciente
              <select required value={pacienteId} onChange={(e) => setPacienteId(e.target.value)}>
                <option value="">Escolher…</option>
                {pacientes.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nome}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <p className="hint">
              <Link to={`/pacientes/${pacienteId}`}>Ver ficha e histórico do paciente</Link>
            </p>
          )}

          <div className="linha-campos">
            <label>
              Data
              <input type="date" required value={data} onChange={(e) => setData(e.target.value)} />
            </label>
            <label>
              Início
              <input type="time" required step={300} value={hora} onChange={(e) => setHora(e.target.value)} />
            </label>
            <label>
              Duração
              <select value={duracao} onChange={(e) => setDuracao(Number(e.target.value))}>
                {[...new Set([...DURACOES, duracao])].sort((a, b) => a - b).map((m) => (
                  <option key={m} value={m}>
                    {m} min
                  </option>
                ))}
              </select>
            </label>
          </div>

          {!nova && (
            <label>
              Estado
              <select value={estado} onChange={(e) => setEstado(e.target.value)}>
                {ESTADOS.map((s) => (
                  <option key={s.valor} value={s.valor}>
                    {s.nome}
                  </option>
                ))}
              </select>
              {automatico && estado === 'realizada' && (
                <span className="hint aviso-confirmar">
                  Passou sozinha a Realizada no fim da hora. Ao guardar, fica confirmada; se não se realizou, escolha
                  Faltou ou Cancelada.
                </span>
              )}
            </label>
          )}

          <label>
            Notas da sessão
            <textarea
              rows={nova ? 3 : 10}
              maxLength={20000}
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              placeholder="Apenas dados fictícios."
            />
          </label>

          <DigitalizarNotas onAcrescentar={(texto) => setNotas((n) => (n.trim() ? `${n.trimEnd()}\n\n${texto}` : texto))} />

          {sobrepostas && (
            <div className="aviso" role="alert">
              <p>
                <strong>Já tem outra consulta neste horário:</strong>{' '}
                {sobrepostas
                  .map((c) => `${nomeDoPaciente(c.paciente_id)} (${formatarHora(new Date(c.inicio))}–${formatarHora(new Date(c.fim))})`)
                  .join(', ')}
              </p>
              <button type="button" disabled={aGuardar} onClick={() => guardar(true)}>
                Marcar mesmo assim
              </button>
            </div>
          )}

          {erro && (
            <p className="error" role="alert">
              {erro}
            </p>
          )}

          <div className="painel-acoes">
            <button type="submit" disabled={aGuardar}>
              {aGuardar ? 'A guardar…' : nova ? 'Marcar' : mudouHorario ? 'Remarcar' : 'Guardar'}
            </button>
            {!nova && estado !== 'cancelada' && (
              <button type="button" className="botao-secundario" disabled={aGuardar} onClick={cancelarConsulta}>
                Cancelar consulta
              </button>
            )}
          </div>
        </form>
      )}
    </aside>
  )
}
