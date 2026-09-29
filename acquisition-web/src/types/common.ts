/** 通用类型：下拉选项、分页、统一响应结构 */

/** 字典选项，value 为后端存储值（如国家用 ISO 代码） */
export interface Option<T = string> {
  label: string
  value: T
}

/** 分页请求参数，所有列表统一服务端分页（CLAUDE.md 8.1） */
export interface PageQuery {
  page: number
  page_size: number
}

/** 分页返回结构 */
export interface PageResult<T> {
  list: T[]
  total: number
  page: number
  page_size: number
}

/** 后端统一响应包装 */
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}
