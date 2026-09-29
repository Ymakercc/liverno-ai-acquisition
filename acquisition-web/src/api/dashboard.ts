/**
 * 获客总览（工作台）接口
 *
 * 与客户画像相同的结构：通过 VITE_USE_MOCK 切换 Mock / 真实接口，
 * 后端就绪后只需关闭开关，页面无需改动。
 *
 * 契约：
 *   GET /liver_api/v1/dashboard/overview
 */
import { request } from './request'
import { fetchDashboardOverviewMock } from '@/mock/dashboard'
import type { DashboardOverview } from '@/types/dashboard'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

/** 获客总览聚合数据：目标完成、核心指标、获客流程、待处理、运行动态 */
export function fetchDashboardOverview(signal?: AbortSignal): Promise<DashboardOverview> {
  if (USE_MOCK) return fetchDashboardOverviewMock()
  return request<DashboardOverview>({
    url: '/dashboard/overview',
    method: 'GET',
    signal
  })
}
