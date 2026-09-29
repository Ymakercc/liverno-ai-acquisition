/**
 * 联系人接口
 *
 * 沿用统一分层：View → API → Mock / Real API。
 *
 * 契约：
 *   GET  /liver_api/v1/contacts
 *   GET  /liver_api/v1/contacts/stats
 *   POST /liver_api/v1/contacts/:id/verify-email
 *   GET  /liver_api/v1/contact-tasks
 *   POST /liver_api/v1/contact-tasks/:id/retry
 *
 * 联系人获取任务由后端在企业具备 relevant 分析并选出 primary_profile 后【自动创建】，
 * 前端不提供手动创建入口，只提供失败重试。
 */
import { request } from './request'
import {
  getContactStatsMock,
  listContactTasksMock,
  listContactsMock,
  retryContactTaskMock,
  verifyContactEmailMock
} from '@/mock/contacts'
import type { PageResult } from '@/types/common'
import type {
  Contact,
  ContactAcquisitionTask,
  ContactQuery,
  ContactStats,
  ContactTaskQuery
} from '@/types/contact'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const BASE = '/contacts'
const TASK_BASE = '/contact-tasks'

/** 联系人列表（服务端分页 + 筛选） */
export function fetchContacts(
  params: ContactQuery,
  signal?: AbortSignal
): Promise<PageResult<Contact>> {
  if (USE_MOCK) return listContactsMock(params)
  return request<PageResult<Contact>>({ url: BASE, method: 'GET', params, signal })
}

/** 顶部统计（含满足待开发条件的企业数） */
export function fetchContactStats(): Promise<ContactStats> {
  if (USE_MOCK) return getContactStatsMock()
  return request<ContactStats>({ url: `${BASE}/stats`, method: 'GET' })
}

/** 重新验证邮箱；验证失败的联系人保留记录 */
export function verifyContactEmail(id: string): Promise<Contact> {
  if (USE_MOCK) return verifyContactEmailMock(id)
  return request<Contact>({ url: `${BASE}/${id}/verify-email`, method: 'POST' })
}

/** 联系人获取任务列表 */
export function fetchContactTasks(params: ContactTaskQuery = {}): Promise<ContactAcquisitionTask[]> {
  if (USE_MOCK) return listContactTasksMock(params)
  return request<ContactAcquisitionTask[]>({ url: TASK_BASE, method: 'GET', params })
}

/** 重新获取联系人（仅失败任务） */
export function retryContactTask(id: string): Promise<ContactAcquisitionTask> {
  if (USE_MOCK) return retryContactTaskMock(id)
  return request<ContactAcquisitionTask>({ url: `${TASK_BASE}/${id}/retry`, method: 'POST' })
}
