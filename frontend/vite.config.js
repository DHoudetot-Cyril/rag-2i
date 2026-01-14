import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // Needed for Docker
    allowedHosts: [
      'insectan-unsinkable-vickey.ngrok-free.dev'
    ],
    proxy: {
      '/query': {
        target: process.env.API_TARGET || 'http://rag_api:8000',
        changeOrigin: true,
      },
      '/documents': {
        target: process.env.API_TARGET || 'http://rag_api:8000',
        changeOrigin: true,
      }
    }
  }
})