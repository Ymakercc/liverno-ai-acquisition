/**
 * 候选企业接口
 *
 * 沿用统一分层：View → API → Mock / Real API，页面不感知 Mock。
 *
 * 契约：
 *   GET  /liver_api/v1/companies
 *   GET  /liver_api/v1/companies/:id
 *   POST /liver_api/v1/companies/:id/reanalyze
 *   GET  /liver_api/v1/companies/stats
 *
 * 发现来源（EnterpriseDiscoverySource）随详情一起返回，不单独拆接口。
 */
import { request } from './request'
import {
  getCompanyMock,
  getCompanyStatsMock,
  listCompaniesMock,
  reanalyzeCompanyMock
} from '@/mock/companies'
import type { PageResult } from '@/types/common'
import type { CompanyQuery, CompanyStats, Enterprise } from '@/types/company'
import type { ResearchDetail } from '@/types/research'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const BASE = '/companies'

/** 候选企业列表（服务端分页 + 筛选） */
export function fetchCompanies(
  params: CompanyQuery,
  signal?: AbortSignal
): Promise<PageResult<Enterprise>> {
  if (USE_MOCK) return listCompaniesMock(params)
  return request<PageResult<Enterprise>>({ url: BASE, method: 'GET', params, signal })
}

/**
 * 企业详情（含全部发现来源与当前画像下的分析）
 * profile_id 决定返回哪个画像语境下的分析结果；不传时由后端取该企业已有分析的默认画像。
 */
export function fetchCompany(
  id: string,
  profileId?: string,
  signal?: AbortSignal
): Promise<Enterprise> {
  if (USE_MOCK) return getCompanyMock(id, profileId)
  return request<Enterprise>({
    url: `${BASE}/${id}`,
    method: 'GET',
    params: profileId ? { profile_id: profileId } : undefined,
    signal
  })
}

/** 单企业背调，只经 Acquisition API 获取；Mock 模式不触发真实服务。 */
export function fetchCompanyResearch(id: string, signal?: AbortSignal): Promise<ResearchDetail> {
  if (USE_MOCK) {
    return Promise.resolve({
      status: 'not_started',
      company: null,
      contacts: [],
      website_research: {
        status: 'not_started', final_url: '', title: '', description: '',
        signals: { meanWellMentioned: false, matchedTerms: [], directFit: false }
      },
      qualification: {
        status: 'not_started', reason: '', reason_code: '', customer_profile: '',
        recommended_products: [], risk_flags: [], failure_reason: ''
      }
    })
  }
  return request<ResearchDetail>({ url: `${BASE}/${id}/research`, method: 'GET', signal })
}

/**
 * 重新触发 AI 相关性分析
 * 相关性是「企业 × 画像」的判断，因此 profile_id 必填；
 * 后端应【追加】一条分析记录而不是覆盖历史，并返回最新一条。
 */
export function reanalyzeCompany(id: string, profileId: string): Promise<Enterprise> {
  if (USE_MOCK) return reanalyzeCompanyMock(id, profileId)
  return request<Enterprise>({
    url: `${BASE}/${id}/reanalyze`,
    method: 'POST',
    data: { profile_id: profileId }
  })
}

/** 顶部统计（画像语境下）；后端未提供时调用方可降级 */
export function fetchCompanyStats(params: {
  task_id?: string
  profile_id?: string
}): Promise<CompanyStats> {
  if (USE_MOCK) return getCompanyStatsMock(params)
  return request<CompanyStats>({ url: `${BASE}/stats`, method: 'GET', params })
}
