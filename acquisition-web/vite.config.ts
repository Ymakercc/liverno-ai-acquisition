import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需引入，避免全量打包
    AutoImport({ resolvers: [ElementPlusResolver()] }),
    Components({ resolvers: [ElementPlusResolver()] })
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    // 只监听本机：外网不可直连，本地通过 SSH 隧道访问
    host: '127.0.0.1',
    port: 5173,
    strictPort: true
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        // 只固定框架层分包；Element Plus 走按需引入，
        // 不在此处整包声明（整包声明会强制打进全量组件）
        manualChunks: {
          vue: ['vue', 'vue-router', 'pinia']
        }
      }
    }
  }
})
