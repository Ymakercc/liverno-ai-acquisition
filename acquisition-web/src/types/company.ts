/**
 * 候选企业类型
 *
 * 核心数据模型原则：
 *
 *   1. Enterprise 是【全局唯一企业实体】，只保存企业自身事实，
 *      不保存任何相关性判断结果。
 *
 *   2. 相关性不是企业的全局属性，而是【企业 × 客户画像】的判断结果：
 *      同一家企业可能对画像 A relevant=true，对画像 B relevant=false。
 *      因此 AI 分析独立为 EnterpriseProfileAnalysis。
 *
 *   3. 企业怎么被发现，由 EnterpriseDiscoverySource 表达（可多条）。
 *
 * 三者关系：
 *   Enterprise 1 ── n EnterpriseDiscoverySource
 *   Enterprise 1 ── n EnterpriseProfileAnalysis（按 profile_id 区分，同一画像可有多次历史）
 */
import type { PageQuery } from './common'

/** AI 分析状态 */
export type AnalysisStatus = 'pending' | 'analyzed' | 'failed'

/** AI 等级：只有 is_relevant = true 时才有意义（CLAUDE.md 9.3） */
export type CompanyGrade = 'A' | 'B' | 'C'

/**
 * 企业 × 画像 维度的 AI 分析结果
 *
 * 每次重新分析【新增一条记录】，不覆盖旧记录；
 * 接口默认返回该 enterprise + profile 下的最新一条。
 * P0 不开发分析历史页面，但数据层必须保留历史。
 *
 * 不相关直接表达为：status = 'analyzed' + is_relevant = false + grade = null，
 * 不引入 not_matched / rejected 这类企业级状态。
 */
export interface EnterpriseProfileAnalysis {
  id: string
  enterprise_id: string
  /** 判断所基于的客户画像 —— 相关性只在该画像语境下成立 */
  profile_id: string
  /** derived / 只读：后端 JOIN CustomerProfile 返回 */
  profile_name?: string

  status: AnalysisStatus
  /** 是否属于该画像的有效目标企业；pending / failed 时为 null */
  is_relevant: boolean | null
  /** A / B / C 优先级；is_relevant !== true 时为 null */
  grade: CompanyGrade | null
  reason: string
  /** 分析失败原因，仅 status = failed 有值 */
  failure_reason?: string
  analyzed_at?: string
}

/**
 * 企业发现来源
 * 记录「这家企业是被哪个任务、通过哪个渠道的哪条 Query 发现的」，同一企业可多条。
 */
export interface EnterpriseDiscoverySource {
  id: string
  enterprise_id: string
  task_id: string
  /** derived / 只读：后端 JOIN AcquisitionTask 返回 */
  task_name: string
  strategy_id: string
  /** 发现时的策略版本快照 */
  strategy_version: number
  channel: string
  query: string
  discovered_at: string
}

/** 列表用的发现来源摘要，避免列表响应携带完整来源数组 */
export interface DiscoverySummary {
  task_count: number
  channels: string[]
  latest_task_id: string
  latest_task_name: string
  latest_discovered_at: string
}

/**
 * 企业实体（全局唯一）
 * 只包含企业自身事实，不含任何画像相关的判断结果。
 */
export interface Enterprise {
  id: string
  company_name: string
  /** 标准化后的企业名称，去重键之一 */
  normalized_name: string
  /** 官网主域名，全局去重第一优先级 */
  domain: string
  website?: string
  /** ISO 3166-1 alpha-2 */
  country: string
  industry: string
  company_type?: string
  /** 邮箱域名，去重辅助判断 */
  email_domain?: string

  first_discovered_at: string
  created_at: string
  updated_at: string

  /* -------- 以下为接口按请求上下文附加的派生数据，非企业自身属性 -------- */

  /**
   * 当前画像语境下的最新一次分析结果。
   * 由请求参数 profile_id（或 task_id 推导出的画像）决定；
   * 该画像下尚无分析记录时为 undefined。
   */
  analysis?: EnterpriseProfileAnalysis

  /** 列表返回：发现来源摘要 */
  discovery_summary: DiscoverySummary
  /** 详情返回：完整发现来源 */
  discovery_sources?: EnterpriseDiscoverySource[]
  /** 详情返回：该企业已有分析记录的画像清单，供详情页切换查看 */
  analysis_profiles?: Array<{ profile_id: string; profile_name: string }>
}

/** AI 相关性筛选值 */
export type RelevanceFilter = 'relevant' | 'not_relevant' | 'pending' | 'failed'

/**
 * 列表查询参数
 *
 * 画像语境的确定顺序（后端需保持一致）：
 *   1. 传了 task_id → 以该任务的 profile_id 为准
 *   2. 否则使用 profile_id
 * relevance / grade 两个筛选都在该画像语境下生效。
 */
export interface CompanyQuery extends PageQuery {
  company_name?: string
  country?: string
  industry?: string
  channel?: string
  task_id?: string
  /** 画像语境；与 task_id 同时存在时以 task_id 推导的画像为准 */
  profile_id?: string
  relevance?: RelevanceFilter
  grade?: CompanyGrade
}

/** 顶部统计（同样是画像语境下的统计） */
export interface CompanyStats {
  total: number
  relevant: number
  not_relevant: number
  pending: number
}
