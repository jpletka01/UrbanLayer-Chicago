import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // The backend's CORS allowlist names :5173. If the port is taken, fail loudly
  // instead of moving to :5174, where every API call would be blocked by CORS.
  server: { port: 5173, strictPort: true },
})
