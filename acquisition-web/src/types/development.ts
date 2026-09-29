/**
 * 待开发客户 / 主画像 契约预留
 *
 * 本文件只定义契约，P0 尚未开发对应页面与接口。
 * 规则来源：CLAUDE.md 9.3.1「相关性语境与主画像」。
 *
 * 核心原则：
 *   相关性按 Enterprise × Profile 判断，
 *   但待开发客户池按 Enterprise 维度管理 —— 同一家企业只能有一条记录。
 */
import type { CompanyGrade, EnterpriseProfileAnalysis } from './company'
import type { ProfilePriority } from './profile'

/**
 * 主画像引用
 *
 * 企业同时匹配多个画像时选出的唯一业务上下文，决定后续：
 * 联系人角色 / 开发信内容 / 产品线 / 应用场景。
 */
export interface PrimaryProfileRef {
  primary_profile_id: string
  /** 选中该画像时所依据的那条分析记录 */
  primary_analysis_id: string
  /** derived / 只读：JOIN CustomerProfile 返回 */
  primary_profile_name?: string
  /** derived / 只读：该分析的等级，便于展示 */
  primary_grade?: CompanyGrade | null
}

/**
 * 待开发客户
 *
 * enterprise_id 必须唯一：同一家企业即使对多个画像 relevant，
 * 待开发客户池也只能存在一条记录，避免重复进入营销链路。
 * 禁止设计成 Enterprise × Profile 维度。
 *
 * 创建时机（三者缺一不可，不是企业刚 relevant 就创建）：
 *   1. 企业存在至少一个 is_relevant = true 的最新分析
 *   2. 联系人获取任务已 completed
 *   3. 该企业至少存在一个 email_verification.status = 'valid' 的联系人
 *
 * 以下一律不得进入：无联系人 / 邮箱全部 invalid / 只有 catch_all /
 * 只有 unknown / 仍有 pending 未完成验证。
 */
export interface DevelopmentCandidate extends PrimaryProfileRef {
  id: string
  /** 唯一键 */
  enterprise_id: string
  /** 进入待开发客户池的时间 */
  entered_at: string
}

/**
 * P0 主画像自动选择规则（后端实现依据，前端不自行计算）
 *
 * 按序比较，先命中先定：
 *   1. is_relevant = true
 *   2. grade：A > B > C
 *   3. grade 相同时：Profile.priority：high > medium > low
 *   4. 仍相同时：analyzed_at 最近的一条
 *
 * 重新分析后若当前主画像变为 not relevant：
 *   仍有其他 relevant 画像 → 自动重选主画像
 *   没有任何 relevant 画像 → 企业不再具备新的待开发资格
 */
export const PRIMARY_PROFILE_RULE_ORDER = [
  'is_relevant',
  'grade',
  'profile_priority',
  'analyzed_at'
] as const

/** 主画像候选：一条 relevant 分析 + 其所属画像的优先级 */
export interface PrimaryProfileCandidate {
  analysis: EnterpriseProfileAnalysis
  profile_priority: ProfilePriority
}

/* -------------------------------------------------------------------------- */
/* 开发就绪度（派生状态，非数据库真源）                                          */
/* -------------------------------------------------------------------------- */

/**
 * 企业进入自动开发链路的就绪度
 *
 * 规则来源：CLAUDE.md 9.3.1「DevelopmentReadiness（派生状态，不落库）」。
 *
 *   ready              AI relevant + 联系人获取完成 + 至少一个 valid 邮箱，
 *                      已具备创建 DevelopmentCandidate 的资格
 *   contact_acquiring  企业 relevant，联系人获取任务为 pending / running
 *   contact_failed     企业 relevant，联系人获取任务为 failed
 *   no_contacts        获取任务已 completed，但没有获取到任何联系人
 *   email_verifying    已有联系人，当前无 valid 邮箱，但至少还有一个 pending
 *   no_valid_email     获取已结束、验证也无待处理项，但 valid email = 0
 *                      （全部 invalid，或只有 catch_all / unknown，或其组合）
 *
 * 重要约定：
 *   1. **这是派生状态，不作为数据库真源字段保存**，按现有数据实时计算，
 *      避免「联系人状态已变、readiness 未同步」的双状态问题
 *   2. 业务真源始终是：Enterprise + EnterpriseProfileAnalysis +
 *      ContactAcquisitionTask + Contact + EmailVerification
 *   3. **禁止**为「待处理企业」新建业务主实体
 *      （BlockedCandidate / PendingCandidate / UnhandledEnterprise 等一律不要）
 *   4. 本类型当前仅作为业务契约预留，未开发对应页面、Mock 与接口
 */
export type DevelopmentReadiness =
  | 'ready'
  | 'contact_acquiring'
  | 'contact_failed'
  | 'no_contacts'
  | 'email_verifying'
  | 'no_valid_email'
