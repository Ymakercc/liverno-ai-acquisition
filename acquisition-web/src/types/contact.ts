/**
 * 联系人类型
 *
 * 业务链路（CLAUDE.md 9.3.1 / 9.4 / 9.11）：
 *   Enterprise → 存在 relevant 分析 → 自动选出 primary_profile
 *   → 自动创建 ContactAcquisitionTask → 获取联系人 → 邮箱验证
 *   → 至少一个 valid email → 才创建 DevelopmentCandidate
 *
 * 核心约定：
 *   1. Contact 归属 enterprise_id，**禁止**出现 profile_id
 *   2. primary_profile 只用于确定本次获取的目标角色，不改变归属
 *   3. 每家企业约 5 名联系人，是【企业级】上限，不是每画像 5 人
 */
import type { PageQuery } from './common'

/**
 * 邮箱验证状态
 * 只有 valid 算「可自动开发邮箱」；catch_all / unknown P0 不允许进入自动营销发送条件。
 */
export type EmailVerificationStatus = 'pending' | 'valid' | 'invalid' | 'catch_all' | 'unknown'

/** 联系人来源类型 */
export type ContactSourceType = 'apollo' | 'website' | 'b2b' | 'other'

/**
 * 联系人来源
 * 同一个联系人可以由多个来源发现，因此来源独立成表，
 * **不在 Contact 上保存单个 source 字段**。
 */
export interface ContactSource {
  id: string
  contact_id: string
  source: ContactSourceType
  source_url?: string
  discovered_at: string
}

/** 邮箱验证结果（属于 Contact） */
export interface EmailVerification {
  status: EmailVerificationStatus
  verified_at?: string
  /** 验证失败/不可用原因 */
  detail?: string
}

/**
 * 联系人
 *
 * 去重规则（同一 Enterprise 内）：
 *   第一优先：normalized_email 完全一致 → 合并为同一个 Contact
 *   第二优先：无邮箱时，normalized_linkedin_url 一致 → 合并
 *   仅姓名 / 职位相似 → **不自动合并**
 */
export interface Contact {
  id: string
  /** 归属企业，唯一归属维度 */
  enterprise_id: string
  /** derived / 只读：后端 JOIN Enterprise 返回 */
  enterprise_name: string
  /** derived / 只读：企业官网主域名，便于核对邮箱域 */
  enterprise_domain?: string

  full_name: string
  title?: string
  department?: string

  email?: string
  /** 去重键：小写去空格后的邮箱 */
  normalized_email?: string
  linkedin_url?: string
  /** 去重键：归一化后的 LinkedIn URL */
  normalized_linkedin_url?: string

  email_verification: EmailVerification

  /** 列表用：来源类型去重后的集合（derived） */
  source_types: ContactSourceType[]
  /** 详情用：完整来源记录 */
  sources?: ContactSource[]

  created_at: string
  updated_at: string
}

/** 联系人获取任务状态 */
export type ContactTaskStatus = 'pending' | 'running' | 'completed' | 'failed'

/**
 * 联系人获取任务
 * 企业具备 relevant 分析并选出 primary_profile 后【自动创建】，
 * 不要求业务人员逐个点击获取；失败时可重新获取。
 */
export interface ContactAcquisitionTask {
  id: string
  enterprise_id: string
  /** derived / 只读 */
  enterprise_name: string

  /** 本次获取所依据的主画像 */
  primary_profile_id: string
  /** derived / 只读 */
  primary_profile_name?: string
  primary_analysis_id: string
  /** 创建时快照的目标联系人角色，来自 primary_profile.target_roles */
  target_roles: string[]

  status: ContactTaskStatus
  found_count: number
  failure_reason?: string

  created_at: string
  started_at?: string
  finished_at?: string
}

/** 联系人列表查询参数 */
export interface ContactQuery extends PageQuery {
  /** 姓名 / 邮箱模糊匹配 */
  keyword?: string
  /** 所属企业精确匹配 */
  enterprise_id?: string
  /** 企业名称模糊匹配 */
  enterprise_name?: string
  /** 职位模糊匹配 */
  title?: string
  email_status?: EmailVerificationStatus
  source?: ContactSourceType
}

/** 获取任务查询参数 */
export interface ContactTaskQuery {
  enterprise_id?: string
  status?: ContactTaskStatus
}

/** 顶部统计 */
export interface ContactStats {
  total: number
  valid: number
  invalid: number
  pending: number
  /**
   * 满足进入待开发客户池条件的企业数：
   * 企业 relevant + 联系人获取完成 + 至少一个 valid 邮箱
   */
  ready_enterprises: number
}
