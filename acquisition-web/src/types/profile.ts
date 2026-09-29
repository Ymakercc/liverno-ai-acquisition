/**
 * 客户画像类型
 * 业务定义：客户画像不是客户档案，它告诉 AI「去互联网寻找什么样的企业」。
 * 链路：客户画像 → AI 搜索策略 → 企业发现（CLAUDE.md 第 2 章）
 */
import type { PageQuery } from './common'

/** 优先级 */
export type ProfilePriority = 'high' | 'medium' | 'low'

/** 客户画像实体 */
export interface CustomerProfile {
  id: string
  /** 画像名称 */
  profile_name: string
  /** 目标行业（多选，字典值） */
  target_industries: string[]
  /** 目标地区（多选，字典值） */
  target_regions: string[]
  /** 目标国家（多选，ISO 3166-1 alpha-2，如 DE / IT / FR） */
  target_countries: string[]
  /** 企业类型（多选） */
  company_types: string[]
  /** 企业规模（单选） */
  company_size: string
  /** 匹配产品线（多选） */
  product_lines: string[]
  /** 目标应用场景（多选 Tag） */
  application_scenarios: string[]
  /** AI 必须满足条件（多条文本） */
  required_signals: string[]
  /** AI 排除条件（多条文本） */
  exclude_signals: string[]
  /** 目标联系人角色（多选） */
  target_roles: string[]
  /** 每日发现配额 */
  daily_quota: number
  /** 优先级 */
  priority: ProfilePriority
  /** 启用状态：true 启用 / false 暂停 */
  is_enabled: boolean
  /** 创建时间 ISO 8601 */
  created_at: string
  /** 更新时间 ISO 8601 */
  updated_at: string
}

/** 新建 / 编辑提交体（不含 id 与时间戳，由后端生成） */
export type ProfilePayload = Omit<CustomerProfile, 'id' | 'created_at' | 'updated_at'>

/** 列表查询参数 */
export interface ProfileQuery extends PageQuery {
  /** 画像名称模糊匹配 */
  profile_name?: string
  /** 目标行业，单值筛选 */
  target_industry?: string
  /** 目标国家 ISO 代码，单值筛选 */
  target_country?: string
  /** 启用状态筛选 */
  is_enabled?: boolean
}

/** 启用 / 暂停提交体 */
export interface ProfileStatusPayload {
  is_enabled: boolean
}
