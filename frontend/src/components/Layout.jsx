import { NavLink, Outlet } from 'react-router'
import { Logo } from './Logo'
import { appEnv, supabase } from '../lib/supabase'
import { useSession } from '../lib/useSession'

export function Layout() {
  const session = useSession()

  return (
    <div className="app">
      <header className="topbar">
        <NavLink to="/" aria-label="Clarity — início">
          <Logo />
        </NavLink>
        <nav aria-label="Navegação principal">
          <NavLink to="/" end>Início</NavLink>
          <NavLink to="/estado">Estado</NavLink>
        </nav>
        <div className="topbar-right">
          {appEnv !== 'production' && (
            <span className="env-badge" title="Ambiente de testes: apenas dados fictícios">
              {appEnv === 'preview' ? 'Pré-visualização' : 'Desenvolvimento'} · dados fictícios
            </span>
          )}
          {session ? (
            <button type="button" className="link-button" onClick={() => supabase.auth.signOut()}>
              Terminar sessão
            </button>
          ) : (
            <NavLink to="/entrar">Iniciar sessão</NavLink>
          )}
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
