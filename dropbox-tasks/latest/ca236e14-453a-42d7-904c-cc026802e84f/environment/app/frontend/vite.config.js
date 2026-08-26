import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '/app/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/query': 'http://localhost:8000',
      '/validate': 'http://localhost:8000',
      '/passages': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/history': 'http://localhost:8000',
    }
  }
})
