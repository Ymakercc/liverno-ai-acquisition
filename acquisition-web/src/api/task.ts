/**
 * 获客任务接口
 *
 * 与画像 / 策略相同结构：通过 VITE_USE_MOCK 切换 Mock / 真实接口，
 * 页面只依赖本文件。
 *
 * 契约：
 *   GET  /liver_api/v1/acquisition-tasks
 *   POST /liver_api/v1/acquisition-tasks
 *   GET  /liver_api/v1/acquisition-tasks/:id
 *   POST /liver_api/v1/acquisition-tasks/:id/start
 *   POST /liver_api/v1/acquisition-tasks/:id/retry
 *   POST /liver_api/v1/acquisition-tasks/:id/pause
 *   GET  /liver_api/v1/acquisition-tasks/stats
 */
import { request } from './request'
import {
  createTaskMock,
  getTaskMock,
  getTaskStatsMock,
  listTasksMock,
  pauseTaskMock,
  retryTaskMock,
  startTaskMock
} from '@/mock/acquisitionTasks'
import type { PageResult } from '@/types/common'
import type { AcquisitionTask, TaskCreatePayload, TaskQuery, TaskStats } from '@/types/task'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const BASE = '/acquisition-tasks'

/** 任务列表（服务端分页 + 筛选） */
export function fetchTasks(
  params: TaskQuery,
  signal?: AbortSignal
): Promise<PageResult<AcquisitionTask>> {
  if (USE_MOCK) return listTasksMock(params)
  return request<PageResult<AcquisitionTask>>({ url: BASE, method: 'GET', params, signal })
}

/** 任务详情 */
export function fetchTask(id: string, signal?: AbortSignal): Promise<AcquisitionTask> {
  if (USE_MOCK) return getTaskMock(id)
  return request<AcquisitionTask>({ url: `${BASE}/${id}`, method: 'GET', signal })
}

/** 创建任务：后端按 strategy_id 取策略并固化快照，创建后为 pending，不自动执行 */
export function createTask(payload: TaskCreatePayload): Promise<AcquisitionTask> {
  if (USE_MOCK) return createTaskMock(payload)
  return request<AcquisitionTask>({ url: BASE, method: 'POST', data: payload })
}

/** 启动任务 */
export function startTask(id: string): Promise<AcquisitionTask> {
  if (USE_MOCK) return startTaskMock(id)
  return request<AcquisitionTask>({ url: `${BASE}/${id}/start`, method: 'POST' })
}

/** 重试失败任务 */
export function retryTask(id: string): Promise<AcquisitionTask> {
  if (USE_MOCK) return retryTaskMock(id)
  return request<AcquisitionTask>({ url: `${BASE}/${id}/retry`, method: 'POST' })
}

/** 暂停执行中的任务 */
export function pauseTask(id: string): Promise<AcquisitionTask> {
  if (USE_MOCK) return pauseTaskMock(id)
  return request<AcquisitionTask>({ url: `${BASE}/${id}/pause`, method: 'POST' })
}

/** 顶部统计；后端未提供时调用方可降级为列表计数 */
export function fetchTaskStats(): Promise<TaskStats> {
  if (USE_MOCK) return getTaskStatsMock()
  return request<TaskStats>({ url: `${BASE}/stats`, method: 'GET' })
}
