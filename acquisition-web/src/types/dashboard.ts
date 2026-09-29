/**
 * 获客总览（工作台）数据类型
 * 口径见 CLAUDE.md 9.1：
 *   发现企业数 = 渠道原始发现
 *   去重企业数 = 标准化去重后
 *   有效企业数 = 去重后且 AI 判断 is_relevant = true —— 每日 300 目标以此为准
 */

/** 今日有效企业目标完成情况 */
export interface DailyGoal {
  /** 统计日期 */
  date: string
  /** 目标值，固定 300 */
  target: number
  /** 当前有效企业数（去重后 + is_relevant = true） */
  current: number
  /** 完成率，百分比数值 */
  rate: number
  /** 是否达标 */
  achieved: boolean
}

/** 指标 / 流程节点的数据来源标记，用于决定是否使用 AI 紫（CLAUDE.md 7.3） */
export type MetricSource = 'system' | 'ai'

/** 核心指标卡 */
export interface CoreMetric {
  key: string
  label: string
  value: number
  /** 指标口径说明 */
  hint: string
  /** 可跳转的目标路由，无则不可点击 */
  to?: string
  source: MetricSource
}

/** 自动获客流程节点 */
export interface FunnelNode {
  key: string
  label: string
  value: number
  to?: string
  source: MetricSource
}

/** 待处理事项的严重级别 */
export type PendingLevel = 'danger' | 'warning' | 'info'

/** 今日待处理 */
export interface PendingTask {
  key: string
  label: string
  count: number
  /** 处理入口 */
  to: string
  level: PendingLevel
}

/** 运行动态状态 */
export type ActivityStatus = 'success' | 'warning' | 'danger' | 'info' | 'ai'

/** 最近运行动态 */
export interface ActivityItem {
  id: string
  /** HH:mm */
  time: string
  title: string
  status: ActivityStatus
}

/** 获客总览聚合数据 */
export interface DashboardOverview {
  goal: DailyGoal
  metrics: CoreMetric[]
  funnel: FunnelNode[]
  pending: PendingTask[]
  activities: ActivityItem[]
}
