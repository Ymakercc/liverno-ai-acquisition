/** 当前登录用户（本阶段为 Mock 结构，后端接入后按 API 契约调整） */
export interface CurrentUser {
  id: string
  name: string
  /** 角色占位：管理员/老板、业务员（CLAUDE.md 9.13） */
  role: 'admin' | 'sales'
  roleLabel: string
}
