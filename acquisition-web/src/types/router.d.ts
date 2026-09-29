import 'vue-router'
import type { MenuGroupKey } from './menu'

declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题，用于面包屑、浏览器标题 */
    title: string
    /** Element Plus 图标组件名 */
    icon?: string
    /** 所属菜单分组 */
    group?: MenuGroupKey
    /** 是否需要登录 */
    requiresAuth: boolean
    /**
     * 权限占位（CLAUDE.md 9.13）：当前仅预留 admin / sales，
     * 本阶段不实现 RBAC。
     */
    permission?: Array<'admin' | 'sales'>
    /** 详情页等非菜单页面，指定高亮的菜单 key */
    activeMenu?: string
    /** 列表页缓存 */
    keepAlive?: boolean
  }
}

export {}
