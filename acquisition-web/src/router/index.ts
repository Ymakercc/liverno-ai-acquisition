import { createRouter, createWebHistory } from 'vue-router'
import { routes } from './routes'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

const APP_TITLE = import.meta.env.VITE_APP_TITLE ?? 'AI 自动获客系统'

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} | ${APP_TITLE}` : APP_TITLE
})

export default router
