import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

// The backend's own allowed origin (api.py SATYASCORE_CORS_ORIGINS default).
const LOCAL_ORIGIN = 'http://localhost:5173'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  // api.py allows this origin in CORS; do not change the port.
  server: {
    port: 5173,
    strictPort: true,
    // Phone mode (npm run dev:phone, VITE_API_URL=/api): the phone talks only to this
    // server, which forwards /api to the backend on the laptop. The backend stays on
    // localhost, never exposed to the network.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
        configure: (proxy) => {
          // A request from this app's own page (Origin = this server) is presented to
          // the backend as the local web app, so its CSRF origin check passes. Any
          // other Origin is passed through unchanged and still refused by the backend.
          proxy.on('proxyReq', (proxyReq, req) => {
            const origin = req.headers.origin
            if (origin && origin === `http://${req.headers.host}`) proxyReq.setHeader('origin', LOCAL_ORIGIN)
          })
        },
      },
    },
  },
})
