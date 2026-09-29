/**
 * 搜索策略接口
 *
 * 与客户画像相同的结构：通过 VITE_USE_MOCK 切换 Mock / 真实接口，
 * 页面只依赖本文件，不感知 Mock 的存在。
 *
 * 契约：
 *   GET   /liver_api/v1/search-strategies
 *   GET   /liver_api/v1/search-strategies/:id
 *   POST  /liver_api/v1/search-strategies/generate
 *   PUT   /liver_api/v1/search-strategies/:id
 *   POST  /liver_api/v1/search-strategies/:id/regenerate
 *   PATCH /liver_api/v1/search-strategies/:id/status
 *   GET   /liver_api/v1/search-strategies/stats
 */
import { request } from './request'
import {
  generateStrategyMock,
  getStrategyMock,
  getStrategyStatsMock,
  listStrategiesMock,
  regenerateStrategyMock,
  updateStrategyMock,
  updateStrategyStatusMock
} from '@/mock/searchStrategies'
import type { PageResult } from '@/types/common'
import type {
  SearchStrategy,
  StrategyGeneratePayload,
  StrategyQuery,
  StrategyStats,
  StrategyStatusPayload,
  StrategyUpdatePayload
} from '@/types/strategy'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const BASE = '/search-strategies'

/** 策略列表（服务端分页 + 筛选） */
export function fetchStrategies(
  params: StrategyQuery,
  signal?: AbortSignal
): Promise<PageResult<SearchStrategy>> {
  if (USE_MOCK) return listStrategiesMock(params)
  return request<PageResult<SearchStrategy>>({ url: BASE, method: 'GET', params, signal })
}

/**
 * 顶部统计
 * 后端未就绪时允许降级：调用方捕获异常后回退到列表接口计数，不阻塞主流程。
 */
export function fetchStrategyStats(): Promise<StrategyStats> {
  if (USE_MOCK) return getStrategyStatsMock()
  return request<StrategyStats>({ url: `${BASE}/stats`, method: 'GET' })
}

/** 策略详情 */
export function fetchStrategy(id: string): Promise<SearchStrategy> {
  if (USE_MOCK) return getStrategyMock(id)
  return request<SearchStrategy>({ url: `${BASE}/${id}`, method: 'GET' })
}

/**
 * AI 生成：只传 profile_id，后端取画像并调用 AI
 * 画像已有策略时返回 version + 1 的预览，不落库；保存后才生效。
 */
export function generateStrategy(payload: StrategyGeneratePayload): Promise<SearchStrategy> {
  if (USE_MOCK) return generateStrategyMock(payload.profile_id)
  return request<SearchStrategy>({ url: `${BASE}/generate`, method: 'POST', data: payload })
}

/** 保存策略（渠道配置 + 状态） */
export function updateStrategy(id: string, payload: StrategyUpdatePayload): Promise<SearchStrategy> {
  if (USE_MOCK) return updateStrategyMock(id, payload)
  return request<SearchStrategy>({ url: `${BASE}/${id}`, method: 'PUT', data: payload })
}

/** 基于当前画像重新生成，返回 version + 1 的预览（不落库，保存后才生效） */
export function regenerateStrategy(id: string): Promise<SearchStrategy> {
  if (USE_MOCK) return regenerateStrategyMock(id)
  return request<SearchStrategy>({ url: `${BASE}/${id}/regenerate`, method: 'POST' })
}

/** 启用 / 暂停 */
export function updateStrategyStatus(
  id: string,
  payload: StrategyStatusPayload
): Promise<SearchStrategy> {
  if (USE_MOCK) return updateStrategyStatusMock(id, payload)
  return request<SearchStrategy>({ url: `${BASE}/${id}/status`, method: 'PATCH', data: payload })
}
