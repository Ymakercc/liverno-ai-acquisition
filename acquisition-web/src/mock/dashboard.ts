/**
 * 获客总览 Mock 数据
 * CLAUDE.md 8.3：Mock 统一放 src/mock，禁止写在 Vue 页面中。
 * 数据结构与后续后端 API 契约保持一致，接入时只替换获取函数。
 */
import type { DashboardOverview } from '@/types/dashboard'

/** 每日有效企业目标（CLAUDE.md 9.1） */
const DAILY_TARGET = 300

/**
 * 今日有效企业数 —— 全局口径
 *
 * = 当天所有获客任务产出的企业，经【全局企业去重】后 is_relevant = true 的唯一企业数。
 * 与单个任务的 relevant_count 不是同一口径：同一家企业被多个任务发现时，
 * 各任务的 relevant_count 都会计数，全局只计一次。
 * 每日 ≥300 家目标只以本指标为准。
 */
const VALID_COMPANIES = 268

export const mockDashboardOverview: DashboardOverview = {
  goal: {
    date: '2026-09-23',
    target: DAILY_TARGET,
    current: VALID_COMPANIES,
    rate: Number(((VALID_COMPANIES / DAILY_TARGET) * 100).toFixed(1)),
    achieved: VALID_COMPANIES >= DAILY_TARGET
  },

  metrics: [
    {
      key: 'discovered',
      label: '原始发现企业',
      value: 1842,
      hint: '各任务渠道原始发现合计，未去重，不计入 300 目标',
      source: 'system'
    },
    {
      key: 'deduplicated',
      label: '去重后企业',
      value: 1126,
      hint: '全局企业去重后（官网主域名 / 名称归一 + 国家）',
      source: 'system'
    },
    {
      key: 'valid',
      label: 'AI 有效企业',
      value: VALID_COMPANIES,
      hint: '全局去重后 is_relevant = true 的唯一企业数',
      to: '/companies',
      source: 'ai'
    },
    {
      key: 'contacts',
      label: '获取联系人',
      value: 982,
      hint: '已补全联系人数量',
      to: '/contacts',
      source: 'system'
    },
    {
      key: 'verified',
      label: '邮箱验证通过',
      value: 613,
      hint: '验证通过才允许自动营销',
      to: '/contacts',
      source: 'system'
    },
    {
      key: 'pushed',
      label: '推送营销',
      value: 608,
      hint: '已推送至营销执行系统',
      to: '/development-pool',
      source: 'system'
    },
    {
      key: 'positive',
      label: '正向客户',
      value: 18,
      hint: 'inquiry / potential_interest',
      to: '/positive-customers',
      source: 'ai'
    },
    {
      key: 'opportunities',
      label: '新增商机',
      value: 6,
      hint: '已创建并同步孚盟 CRM',
      to: '/opportunities',
      source: 'system'
    }
  ],

  funnel: [
    { key: 'discover', label: '企业发现', value: 1842, to: '/acquisition-tasks', source: 'system' },
    { key: 'dedupe', label: '去重', value: 1126, source: 'system' },
    { key: 'ai-filter', label: 'AI 筛选', value: 268, to: '/companies', source: 'ai' },
    { key: 'contact', label: '联系人', value: 982, to: '/contacts', source: 'system' },
    { key: 'verify', label: '邮箱验证', value: 613, to: '/contacts', source: 'system' },
    {
      key: 'marketing',
      label: '自动营销',
      value: 608,
      to: '/development-pool',
      source: 'system'
    },
    {
      key: 'positive',
      label: '正向客户',
      value: 18,
      to: '/positive-customers',
      source: 'ai'
    },
    { key: 'assign', label: '客户分配', value: 12, to: '/positive-customers', source: 'system' },
    { key: 'opportunity', label: '商机', value: 6, to: '/opportunities', source: 'system' }
  ],

  pending: [
    { key: 'task-failed', label: '获客任务失败', count: 2, to: '/acquisition-tasks', level: 'danger' },
    { key: 'verify-failed', label: '邮箱验证失败', count: 37, to: '/contacts', level: 'warning' },
    { key: 'push-failed', label: '营销推送失败', count: 5, to: '/development-pool', level: 'danger' },
    {
      key: 'assign-pending',
      label: '待确认客户分配',
      count: 6,
      to: '/positive-customers',
      level: 'warning'
    },
    { key: 'crm-failed', label: 'CRM 同步失败', count: 1, to: '/opportunities', level: 'danger' }
  ],

  activities: [
    { id: 'a1', time: '14:26', title: '孚盟 CRM 同步失败：商机 OPP-20260923-003', status: 'danger' },
    { id: 'a2', time: '14:02', title: '正向客户新增 2 家，已停止该企业全部自动营销', status: 'ai' },
    { id: 'a3', time: '13:40', title: '邮箱验证批次完成：通过 148 / 失败 37', status: 'warning' },
    { id: 'a4', time: '12:15', title: '已向营销执行系统推送 216 个验证通过联系人', status: 'success' },
    { id: 'a5', time: '11:08', title: 'AI 企业分析完成：有效 268 家，不匹配 858 家', status: 'ai' },
    { id: 'a6', time: '09:30', title: '获客任务「印度 PCB 连接器 - Google」执行完成', status: 'success' },
    { id: 'a7', time: '09:12', title: '获客任务「TradeIndia 电源模块」执行失败：渠道超时', status: 'danger' }
  ]
}

/**
 * 获取获客总览数据（当前为 Mock）
 * 后端接入后替换为 src/api/dashboard.ts 中的真实请求，页面调用方式不变。
 */
export function fetchDashboardOverviewMock(): Promise<DashboardOverview> {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve(mockDashboardOverview), 300)
  })
}
