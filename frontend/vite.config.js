import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',   // Required: bind to all interfaces inside Docker
    port: 5173,
    // Proxy /api requests to the backend service
    // This avoids CORS issues during development
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})
