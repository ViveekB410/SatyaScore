import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Port 5173 is the one api.py's CORS config already allows — do not change it.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
})
