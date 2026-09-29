/**
 * 搜索策略类型
 *
 * 业务定位（CLAUDE.md 第 2 章）：
 *   客户画像回答「我们要找什么样的企业」
 *   搜索策略回答「AI 通过什么渠道、用什么搜索条件找到这些企业」
 *
 * 链路：客户画像 → AI 生成搜索策略 → 人工调整 → 启用 → 创建获客任务 → 企业发现
 * 模型约定：一个客户画像对应一套当前搜索策略，一套策略内含多个渠道策略。
 */
import type { PageQuery } from './common'

/** 策略状态：草稿 / 启用 / 暂停。仅 active 可用于创建新的获客任务 */
export type StrategyStatus = 'draft' | 'active' | 'paused'

/** 单条搜索 Query */
export interface SearchQuery {
  id: string
  /** 实际投放到渠道的搜索式 */
  query_text: string
  /** 目标国家 ISO 3166-1 alpha-2 */
  country_code?: string
  /** 搜索语言，如 de / en / it */
  language?: string
  /** 单条 Query 可独立启停 */
  enabled: boolean
}

/** 渠道级策略；channel 取值来自渠道字典，禁止在页面内硬编码判断 */
export interface ChannelSearchStrategy {
  channel: string
  /** 渠道可独立启停 */
  enabled: boolean
  queries: SearchQuery[]
  target_countries: string[]
  /** AI 给出的该渠道打法说明 */
  strategy_summary?: string
}

/** 搜索策略实体 */
export interface SearchStrategy {
  id: string
  /**
   * 关联的客户画像 —— 唯一关联真源。
   * SearchStrategy 只维护 profile_id，不承担画像信息的一致性维护职责。
   */
  profile_id: string
  /**
   * derived / 只读：后端按 profile_id JOIN CustomerProfile 实时返回。
   * 不是 SearchStrategy 自己维护的业务字段，画像改名后自动跟随最新值，
   * 前端不得提交该字段。历史名称快照应由 AcquisitionTask 自行保存。
   */
  profile_name: string
  status: StrategyStatus
  /**
   * derived / 只读：同样来自 JOIN CustomerProfile。
   * 画像暂停不会修改本策略的 status，但会阻断新获客任务的产生，
   * 列表需区分「人工暂停策略」与「受上游画像暂停影响」两个概念。
   */
  profile_enabled?: boolean
  /** 每次重新生成 +1，供获客任务记录 strategy_version 追溯 */
  version: number
  /**
   * 乐观锁基准版本：generate / regenerate / 详情返回时给出，
   * 代表本次编辑所基于的服务端版本。保存时必须原样回传。
   */
  base_version?: number
  channel_strategies: ChannelSearchStrategy[]
  created_at: string
  updated_at: string
}

/** 列表查询参数 */
export interface StrategyQuery extends PageQuery {
  /** 来源画像名称模糊匹配 */
  profile_name?: string
  /** 按画像精确查询，用于判断该画像是否已存在策略 */
  profile_id?: string
  /** 渠道筛选：命中条件为该渠道存在于 channel_strategies */
  channel?: string
  status?: StrategyStatus
}

/** AI 生成：前端只传画像 id，后端自行取画像并调用 AI */
export interface StrategyGeneratePayload {
  profile_id: string
}

/**
 * 保存提交体
 *
 * 版本语义：AI 重新生成只返回预览、不落库，真正落库发生在本接口。
 * 前端回传预览版本号：
 *   version > 当前版本 → 作为新版本提交（来自重新生成）
 *   version === 当前版本 → 普通编辑，版本不变
 * 历史获客任务记录的 strategy_version 不得被新版本影响。
 */
export interface StrategyUpdatePayload {
  channel_strategies: ChannelSearchStrategy[]
  status: StrategyStatus
  /** 本次要落库的版本号（重新生成预览为 base_version + 1，普通编辑等于 base_version） */
  version: number
  /**
   * 乐观锁：本次编辑所基于的服务端版本。
   * 后端校验 DB.version === base_version，不一致返回 409 + STRATEGY_VERSION_CONFLICT，
   * 禁止静默覆盖他人的修改。普通编辑同样必须携带。
   */
  base_version: number
}

/** 顶部统计 */
export interface StrategyStats {
  total: number
  active: number
  draft: number
  paused: number
}

/** 启用 / 暂停提交体 */
export interface StrategyStatusPayload {
  status: StrategyStatus
}

/* -------------------------------------------------------------------------- */
/* 启用校验（业务规则，前后端共用同一口径）                                     */
/* -------------------------------------------------------------------------- */

/** 启用失败时的统一提示文案 */
export const ACTIVATE_HINT = '至少启用一个搜索渠道，并保留一条有效搜索 Query。'

/** 编辑 active 策略时保存失败的提示文案 */
export const ACTIVE_EDIT_HINT =
  '当前策略处于启用状态，至少需要一个启用渠道和一条有效搜索 Query。'

/** 版本冲突业务错误码，对应 HTTP 409 */
export const STRATEGY_VERSION_CONFLICT = 'STRATEGY_VERSION_CONFLICT'

/** 版本冲突提示文案 */
export const VERSION_CONFLICT_HINT = '该搜索策略已被其他用户更新，请刷新后重新操作。'

/**
 * draft → active 的完整校验：
 *   1. 至少一个 enabled = true 的渠道
 *   2. 该启用渠道内至少一条 enabled = true 且 query_text 非空的 Query
 *
 * 保存为 draft 允许配置不完整；进入 active 必须通过本校验。
 * 前端做即时反馈，后端仍须独立校验，不得以前端校验替代。
 */
export function canActivate(channels: ChannelSearchStrategy[]): boolean {
  return channels.some(
    (channel) =>
      channel.enabled &&
      channel.queries.some((query) => query.enabled && query.query_text.trim().length > 0)
  )
}
