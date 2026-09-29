/**
 * 统一请求封装（CLAUDE.md 5.2）
 * - Base Path 由环境变量注入，禁止业务代码硬编码
 * - 统一处理 token、错误码、请求取消（AbortController）
 * - 禁止页面内直接使用 axios
 */
import axios, { type AxiosRequestConfig, type AxiosInstance } from 'axios'
import type { ApiResponse } from '@/types/common'

/**
 * 统一错误对象
 * 业务层通过 status / code 判断具体场景（如 409 版本冲突），
 * 不要用 message 文本匹配。Mock 服务同样抛出本类型，保证前端处理路径一致。
 */
export class ApiError extends Error {
  status?: number
  code?: string

  constructor(message: string, status?: number, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

const instance: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 20000
})

instance.interceptors.request.use((config) => {
  // 认证尚未接入，token 位置先预留，后续从 user store 读取
  const token = localStorage.getItem('app:token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

instance.interceptors.response.use(
  (response) => {
    const payload = response.data as ApiResponse<unknown>
    // 约定 code === 0 为成功，其余交由调用方捕获
    if (payload && typeof payload.code === 'number' && payload.code !== 0) {
      return Promise.reject(
        new ApiError(payload.message || '请求失败', response.status, String(payload.code))
      )
    }
    return response
  },
  (error) => {
    // 非 2xx：透传 HTTP 状态码与后端业务错误码，供调用方精确判断
    if (axios.isAxiosError(error)) {
      const status = error.response?.status
      const body = error.response?.data as { message?: string; code?: string | number } | undefined
      return Promise.reject(
        new ApiError(
          body?.message || error.message || '请求失败',
          status,
          body?.code !== undefined ? String(body.code) : undefined
        )
      )
    }
    return Promise.reject(error)
  }
)

/** 统一解包 data，业务层只拿到实际数据 */
export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const response = await instance.request<ApiResponse<T>>(config)
  return response.data.data
}

export default instance
