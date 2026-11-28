import { createBrowserRouter, RouterProvider } from 'react-router'
import { Layout } from './components/Layout'
import { Inicio } from './pages/Inicio'
import { Estado } from './pages/Estado'
import { Entrar } from './pages/Entrar'
import { Pacientes } from './pages/Pacientes'
import { Paciente } from './pages/Paciente'
import { Agenda } from './pages/Agenda'
import { NaoEncontrado } from './pages/NaoEncontrado'
import { appEnv } from './lib/supabase'

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Inicio /> },
      { path: '/agenda', element: <Agenda /> },
      { path: '/pacientes', element: <Pacientes /> },
      { path: '/pacientes/:id', element: <Paciente /> },
      // Página técnica para a equipa (API, ambiente, versão): não existe na versão online.
      ...(appEnv === 'production' ? [] : [{ path: '/estado', element: <Estado /> }]),
      { path: '/entrar', element: <Entrar /> },
      { path: '*', element: <NaoEncontrado /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
