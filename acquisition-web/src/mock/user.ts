/** Mock 数据统一放此目录，禁止写在 Vue 页面中（CLAUDE.md 8.3） */
import type { CurrentUser } from '@/types/user'

export const mockCurrentUser: CurrentUser = {
  id: 'mock-admin',
  name: '管理员',
  role: 'admin',
  roleLabel: '管理员'
}
