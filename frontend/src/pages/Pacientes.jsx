import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../lib/api'
import { useSession } from '../lib/useSession'

// Lista e criação de pacientes. Só DADOS FICTÍCIOS até haver DPIA aprovada.
// Quem garante que cada psicólogo só vê os seus é a base de dados (RLS), não esta página.

function formatarData(iso) {
  if (!iso) return '—'
  const [ano, mes, dia] = iso.split('-')
  return `${dia}/${mes}/${ano}`
}

export function Pacientes() {
  const session = useSession()
  const [pacientes, setPacientes] = useState(null)
  const [verArquivados, setVerArquivados] = useState(false)
  const [recarregar, setRecarregar] = useState(0)
  const [erro, setErro] = useState(null)
  const [nome, setNome] = useState('')
  const [dataNascimento, setDataNascimento] = useState('')
  const [aGuardar, setAGuardar] = useState(false)

  useEffect(() => {
    if (!session) return
    api(`/api/pacientes${verArquivados ? '?arquivados=true' : ''}`)
      .then((lista) => {
        setPacientes(lista)
        setErro(null)
      })
      .catch((e) => setErro(e.message))
  }, [session, verArquivados, recarregar])

  async function criar(e) {
    e.preventDefault()
    setErro(null)
    setAGuardar(true)
    try {
      await api('/api/pacientes', {
        method: 'POST',
        body: JSON.stringify({ nome, data_nascimento: dataNascimento || null }),
      })
      setNome('')
      setDataNascimento('')
      setRecarregar((n) => n + 1)
    } catch (err) {
      setErro(err.message)
    } finally {
      setAGuardar(false)
    }
  }

  async function mudarArquivo(paciente) {
    setErro(null)
    try {
      await api(`/api/pacientes/${paciente.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ ativo: !paciente.ativo }),
      })
      setRecarregar((n) => n + 1)
    } catch (err) {
      setErro(err.message)
    }
  }

  if (session === undefined) return <p>A carregar…</p>
  if (!session) {
    return (
      <section>
        <h1>Pacientes</h1>
        <p>
          <Link to="/entrar">Inicie sessão</Link> para ver os seus pacientes.
        </p>
      </section>
    )
  }

  return (
    <section>
      <h1>Pacientes</h1>
      <p className="hint">Apenas dados fictícios. Nunca introduzir dados de pacientes reais.</p>

      <form onSubmit={criar} className="form form-inline">
        <label>
          Nome
          <input required maxLength={120} value={nome} onChange={(e) => setNome(e.target.value)} />
        </label>
        <label>
          Data de nascimento (opcional)
          <input type="date" min="1900-01-01" value={dataNascimento} onChange={(e) => setDataNascimento(e.target.value)} />
        </label>
        <button type="submit" disabled={aGuardar}>{aGuardar ? 'A guardar…' : 'Adicionar'}</button>
      </form>

      {erro && <p className="error" role="alert">{erro}</p>}

      <label className="checkbox">
        <input type="checkbox" checked={verArquivados} onChange={(e) => setVerArquivados(e.target.checked)} />
        Mostrar arquivados
      </label>

      {pacientes === null ? (
        !erro && <p>A carregar…</p>
      ) : pacientes.length === 0 ? (
        <p>Ainda não tem pacientes.</p>
      ) : (
        <table className="tabela">
          <thead>
            <tr>
              <th>Nome</th>
              <th>Data de nascimento</th>
              <th>Estado</th>
              <th aria-label="Ações" />
            </tr>
          </thead>
          <tbody>
            {pacientes.map((p) => (
              <tr key={p.id}>
                <td>
                  <Link to={`/pacientes/${p.id}`}>{p.nome}</Link>
                </td>
                <td>{formatarData(p.data_nascimento)}</td>
                <td>{p.ativo ? 'Ativo' : 'Arquivado'}</td>
                <td>
                  <button type="button" className="link-button" onClick={() => mudarArquivo(p)}>
                    {p.ativo ? 'Arquivar' : 'Reativar'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
