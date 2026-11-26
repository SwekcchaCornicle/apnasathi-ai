import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api/v1': {
        target: 'http://apnasathi-dev-alb-791654695.ap-south-1.elb.amazonaws.com',
        changeOrigin: true,
      },
    },
  },
})
