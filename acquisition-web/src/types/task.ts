/**
 * 获客任务类型
 *
 * 业务链路（CLAUDE.md 第 2 章）：
 *   客户画像 → 搜索策略 → 创建获客任务 → 执行 → 企业发现 → 标准化/去重 → AI 有效企业 → 候选企业库
 *
 * 核心约定：任务创建时快照 strategy_id + strategy_version，
 * 策略后续重新生成不影响已创建的历史任务。
 */
import type { PageQuery } from './common'

/** P0 简单状态，不做复杂状态机 */
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'

/** 执行单元状态 */
export type TaskQueryUnitStatus = 'pending' | 'running' | 'completed' | 'failed'

/**
 * 执行单元：任务按 Channel + Query 拆分后的最小调度粒度
 *
 * 用途是支持「暂停 → 继续」而不是整体重跑：
 *   暂停：不再调度 pending 单元；正在 running 的单元允许执行完成并保存结果
 *   继续：只执行剩余 pending / 需重试的单元
 *
 * P0 只做到 Query 级断点，**不做搜索结果页级（page / cursor）断点**。
 * 渠道内部若存在分页，允许该 Query 整体重跑，靠企业全局去重避免重复入库。
 *
 * 前端 P0 不展示执行单元列表，该结构用于对齐后端契约与进度回写。
 */
export interface TaskQueryUnit {
  id: string
  channel: string
  /** 对应策略快照中的 Query 文本 */
  query_text: string
  status: TaskQueryUnitStatus
  /** 该单元返回的原始结果数 */
  raw_discovered_count: number
  started_at?: string
  finished_at?: string
  failure_reason?: string
}

/** 并发冲突业务错误码，对应 HTTP 409 */
export const TASK_STRATEGY_BUSY = 'TASK_STRATEGY_BUSY'

/** 并发冲突提示文案 */
export const TASK_STRATEGY_BUSY_HINT =
  '该搜索策略版本当前已有执行中或暂停中的获客任务。'

/**
 * 渠道执行快照
 * 创建任务时从策略复制，之后不随策略新版本变化，保证历史可追溯。
 */
export interface TaskChannelSnapshot {
  channel: string
  /** Query 文本快照，用于展示「当时用什么搜索式跑的」 */
  queries: string[]
  target_countries: string[]
  /** 该渠道原始结果数，由其下各执行单元汇总 */
  raw_discovered_count: number
}

/** 本次任务观察到的 SearchResult；同一结果可同时属于多个任务。 */
export interface TaskSearchResult {
  id: string
  title: string
  url: string
  result_domain?: string
  query_text: string
  rank: number
  observed_at: string
}

/** 获客任务实体 */
export interface AcquisitionTask {
  id: string
  task_name: string

  /** 关联真源 */
  profile_id: string
  strategy_id: string
  /** derived / 只读：SearchStrategy.code */
  strategy_code: string
  /** 创建时的策略版本快照，历史任务永不变更 */
  strategy_version: number

  /** derived / 只读：后端 JOIN CustomerProfile 返回，前端不得提交 */
  profile_name: string

  status: TaskStatus

  max_queries: number
  results_per_query: number
  enterprise_target: number

  queries_executed: number
  search_results_count: number
  valid_domains_count: number
  new_enterprises_count: number
  duplicate_enterprises_count: number

  /** 执行渠道快照 */
  channel_snapshots: TaskChannelSnapshot[]
  /** Query 总数（快照） */
  query_count: number
  /** 目标国家（快照，各渠道去重合并） */
  target_countries: string[]
  /** 详情返回：由 acquisition_task_search_result 关联读取。 */
  search_results?: TaskSearchResult[]

  /* -------- 获客结果：任务级指标 --------
   *
   * 注意口径：这三个数字都是【任务内部】的统计，用于评价本次任务
   * （搜索策略质量 / Query 质量 / 渠道效果），与 Dashboard 的每日目标不是同一口径。
   *
   *   raw_discovered_count  = 本任务各渠道返回的原始结果数量
   *   deduplicated_count    = 本任务【内部】去重后的企业数
   *   relevant_count        = 本任务内部去重 + AI is_relevant 后的企业数
   *
   * Dashboard「今日有效企业」= 当天所有任务结果经【全局企业去重】后
   * is_relevant = true 的唯一企业数，每日 ≥300 家目标只以该全局指标为准。
   *
   * 因此「任务 A 80 + 任务 B 70 = 150，而全局只有 130」是正常且预期的。
   */
  /** 原始结果数，不去重，不计入每日 300 目标 */
  raw_discovered_count: number
  /** 任务内部去重后的企业数 */
  deduplicated_count: number
  /**
   * 任务内部去重 + AI 判断有效的企业数（任务级，非全局口径）
   *
   * 真源定义：本任务关联的去重企业中，针对【该任务的 profile_id】，
   * 最新一次分析结果 is_relevant = true 的唯一企业数。
   *
   * 即由「任务-企业发现关系」+「企业 × 画像 维度的 AI 分析」回算得到。
   * 允许后端缓存该计数，但**不得维护一个与关系数据脱节的独立计数器**；
   * 重新分析导致判断翻转时，该计数必须随之变化。
   */
  relevant_count: number

  /**
   * 执行单元（Channel + Query 粒度）
   * 支撑暂停后继续执行；前端 P0 不渲染，仅作为契约与进度来源。
   */
  query_units?: TaskQueryUnit[]

  /** 失败原因，仅 failed 状态有值 */
  failure_reason?: string

  created_at: string
  started_at?: string
  finished_at?: string
  updated_at: string
}

/** 创建任务提交体：最少字段，其余由后端按策略快照填充 */
export interface TaskCreatePayload {
  task_name: string
  strategy_id: string
  max_queries: number
  results_per_query: number
  enterprise_target: number
}

/** 列表查询参数 */
export interface TaskQuery extends PageQuery {
  task_name?: string
  profile_name?: string
  strategy_id?: string
  status?: TaskStatus
}

/** 顶部统计 */
export interface TaskStats {
  total: number
  pending: number
  running: number
  completed: number
  failed: number
}
