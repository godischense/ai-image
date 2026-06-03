import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  base: './',
  build: {
    outDir: '../www'
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        api: 'modern',
        silenceDeprecations: ['legacy-js-api', 'import'],
        additionalData: (content, filePath) => {
          if (filePath.endsWith('variables.scss') || filePath.endsWith('mixins.scss') || filePath.endsWith('common.scss')) {
            return content
          }
          return `@use "@/styles/variables" as *;\n@use "@/styles/mixins" as *;\n${content}`
        }
      }
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5678',
        changeOrigin: true
      }
    }
  }
})
