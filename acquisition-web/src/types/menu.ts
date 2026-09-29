/** 侧边栏菜单类型定义 */

/** 菜单分组 key，用于 Header 面包屑与菜单高亮 */
export type MenuGroupKey =
  | 'workbench'
  | 'acquisition'
  | 'customer'
  | 'opportunity'
  | 'system'

/** 叶子菜单项 */
export interface MenuItem {
  /** 唯一标识，同时作为 el-menu 的 index */
  key: string
  /** 菜单显示名 */
  title: string
  /** 跳转路由 path */
  path: string
  /** Element Plus 图标组件名（线性风格） */
  icon: string
}

/** 一级菜单：可以是单项入口，也可以是带子菜单的分组 */
export interface MenuGroup {
  key: MenuGroupKey
  title: string
  icon: string
  /** 单项入口时直接给 path；分组则给 children */
  path?: string
  children?: MenuItem[]
  /** 是否固定在侧边栏底部区域（系统类菜单） */
  bottom?: boolean
}
