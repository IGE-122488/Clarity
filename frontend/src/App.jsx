import { createBrowserRouter, RouterProvider } from 'react-router'
import { Layout } from './components/Layout'
import { Inicio } from './pages/Inicio'
import { Estado } from './pages/Estado'
import { Entrar } from './pages/Entrar'
import { Pacientes } from './pages/Pacientes'
import { NaoEncontrado } from './pages/NaoEncontrado'

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Inicio /> },
      { path: '/pacientes', element: <Pacientes /> },
      { path: '/estado', element: <Estado /> },
      { path: '/entrar', element: <Entrar /> },
      { path: '*', element: <NaoEncontrado /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
