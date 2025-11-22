import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // Needed for Docker
    proxy: {
      '/query': {
        target: 'http://rag_api:8000',
        changeOrigin: true,
      },
      '/documents': {
        target: 'http://rag_api:8000',
        changeOrigin: true,
      }
    }
  }
})
