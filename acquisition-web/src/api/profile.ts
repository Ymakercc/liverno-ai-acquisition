/**
 * 客户画像接口
 *
 * 当前后端尚未就绪，通过 VITE_USE_MOCK 切换到 Mock 服务。
 * 真实接口上线后只需把 .env 中的 VITE_USE_MOCK 置为 false，
 * 页面、类型、调用方式均不需要任何改动。
 *
 * 契约：
 *   GET    /liver_api/v1/profiles
 *   POST   /liver_api/v1/profiles
 *   GET    /liver_api/v1/profiles/:id
 *   PUT    /liver_api/v1/profiles/:id
 *   PATCH  /liver_api/v1/profiles/:id/status
 */
import { request } from './request'
import {
  createProfileMock,
  getProfileMock,
  listProfilesMock,
  updateProfileMock,
  updateProfileStatusMock
} from '@/mock/profiles'
import type { PageResult } from '@/types/common'
import type {
  CustomerProfile,
  ProfilePayload,
  ProfileQuery,
  ProfileStatusPayload
} from '@/types/profile'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

/** 画像列表（服务端分页 + 筛选） */
export function fetchProfiles(
  params: ProfileQuery,
  signal?: AbortSignal
): Promise<PageResult<CustomerProfile>> {
  if (USE_MOCK) return listProfilesMock(params)
  return request<PageResult<CustomerProfile>>({
    url: '/profiles',
    method: 'GET',
    params,
    signal
  })
}

/** 画像详情 */
export function fetchProfile(id: string): Promise<CustomerProfile> {
  if (USE_MOCK) return getProfileMock(id)
  return request<CustomerProfile>({ url: `/profiles/${id}`, method: 'GET' })
}

/** 新建画像 */
export function createProfile(payload: ProfilePayload): Promise<CustomerProfile> {
  if (USE_MOCK) return createProfileMock(payload)
  return request<CustomerProfile>({ url: '/profiles', method: 'POST', data: payload })
}

/** 编辑画像 */
export function updateProfile(id: string, payload: ProfilePayload): Promise<CustomerProfile> {
  if (USE_MOCK) return updateProfileMock(id, payload)
  return request<CustomerProfile>({ url: `/profiles/${id}`, method: 'PUT', data: payload })
}

/** 启用 / 暂停 */
export function updateProfileStatus(
  id: string,
  payload: ProfileStatusPayload
): Promise<CustomerProfile> {
  if (USE_MOCK) return updateProfileStatusMock(id, payload)
  return request<CustomerProfile>({ url: `/profiles/${id}/status`, method: 'PATCH', data: payload })
}
