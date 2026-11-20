import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Em desenvolvimento, os pedidos para /api vão para a API em Python (uvicorn, porta 8000).
// Assim o frontend usa sempre caminhos relativos (/api/...) e não há problemas de CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
