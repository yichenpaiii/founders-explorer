import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy API to Cloudflare Pages Functions dev server
      // Use `wrangler pages dev ./client` to run the Functions locally
      '/api': 'http://127.0.0.1:8788'
    }
  }
})
