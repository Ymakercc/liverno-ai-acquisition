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
 *   POST /liver_api/v1/acquisition-tasks/:id/run
 *   GET  /liver_api/v1/acquisition-tasks/stats
 */
import { request } from './request'
import {
  createTaskMock,
  getTaskMock,
  getTaskStatsMock,
  listTasksMock,
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

/** 同步执行一次真实企业发现 */
export function runTask(id: string): Promise<AcquisitionTask> {
  if (USE_MOCK) return startTaskMock(id)
  return request<AcquisitionTask>({ url: `${BASE}/${id}/run`, method: 'POST' })
}

/** 顶部统计；后端未提供时调用方可降级为列表计数 */
export function fetchTaskStats(): Promise<TaskStats> {
  if (USE_MOCK) return getTaskStatsMock()
  return request<TaskStats>({ url: `${BASE}/stats`, method: 'GET' })
}
