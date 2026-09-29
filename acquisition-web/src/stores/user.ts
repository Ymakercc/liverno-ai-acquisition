/**
 * 用户状态（本阶段仅 Mock，不实现登录认证与真实权限 —— 见 CLAUDE.md 第 11 章）
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { mockCurrentUser } from '@/mock/user'
import type { CurrentUser } from '@/types/user'

export const useUserStore = defineStore('user', () => {
  const currentUser = ref<CurrentUser>(mockCurrentUser)
  return { currentUser }
})
