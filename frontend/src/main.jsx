import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Letras alojadas na própria app (sem pedidos ao Google Fonts, que enviariam o IP dos utilizadores)
import '@fontsource-variable/outfit'
import '@fontsource-variable/atkinson-hyperlegible-next'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
