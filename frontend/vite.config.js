import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    open: true,
    // Enable SPA fallback for client-side routing
    historyApiFallback: true
  },
  // Handle SPA routing in preview mode
  preview: {
    port: 3001
  }
})
