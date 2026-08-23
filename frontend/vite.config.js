import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'

// Safely detect if running inside a Docker container
let isDocker = false
try {
  isDocker = fs.existsSync('/.dockerenv') || 
             (fs.existsSync('/proc/1/cgroup') && 
              fs.readFileSync('/proc/1/cgroup', 'utf-8').includes('docker'))
} catch (_) {
  isDocker = false
}

// Fallback to localhost if running on developer machine host directly
const proxyTarget = process.env.BACKEND_URL || (isDocker ? 'http://backend:8000' : 'http://localhost:8000')

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',   // Required: bind to all interfaces inside Docker
    port: 5173,
    // Proxy /api requests to the backend service
    // This avoids CORS issues during development
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
})
