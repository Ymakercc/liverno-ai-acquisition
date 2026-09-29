/**
 * 获客任务 Mock 服务
 * CLAUDE.md 8.3：Mock 统一放 src/mock，禁止写在 Vue 页面中。
 *
 * 模拟服务端语义：分页、筛选、创建、启动、暂停、重试，
 * 以及 pending → running → completed 的执行过程与三个结果数字的递增。
 * 执行用简单定时器推进，不做复杂调度系统。
 */
import { getProfileMetaMock } from './profiles'
import { getStrategyMock } from './searchStrategies'
import { ApiError } from '@/api/request'
import { TASK_STRATEGY_BUSY, TASK_STRATEGY_BUSY_HINT } from '@/types/task'
import type { PageResult } from '@/types/common'
import type {
  AcquisitionTask,
  TaskChannelSnapshot,
  TaskCreatePayload,
  TaskQuery,
  TaskQueryUnit,
  TaskStats,
  TaskStatus
} from '@/types/task'

const LATENCY = 300
/** 执行推进节奏：每 2.5s 完成一个执行单元（Channel + Query） */
const TICK_INTERVAL = 2500

function delay<T>(data: T, ms: number = LATENCY): Promise<T> {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve(data), ms)
  })
}

function now(): string {
  const date = new Date()
  const pad = (value: number): string => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

/** 结果数字的经验转化率：原始发现 → 去重 → AI 有效 */
const DEDUPE_RATE = 0.62
const RELEVANT_RATE = 0.24

/** 单条 Query 的预期原始结果数，做一点确定性抖动，避免数字过于整齐 */
function expectedRawPerQuery(index: number): number {
  return 34 + ((index * 13) % 26)
}

let unitSeed = 0
function makeUnit(channel: string, queryText: string): TaskQueryUnit {
  unitSeed += 1
  return {
    id: `TQU-${String(unitSeed).padStart(5, '0')}`,
    channel,
    query_text: queryText,
    status: 'pending',
    raw_discovered_count: 0
  }
}

/** 由渠道快照拆出执行单元：任务的最小调度粒度 */
function buildUnits(snapshots: TaskChannelSnapshot[]): TaskQueryUnit[] {
  return snapshots.flatMap((snapshot) =>
    snapshot.queries.map((query) => makeUnit(snapshot.channel, query))
  )
}

/**
 * 由执行单元回算任务聚合值
 * 保证「任务/渠道数字」始终等于已完成单元之和，暂停后继续不会出现数字回退。
 */
function syncAggregates(task: AcquisitionTask): void {
  const units = task.query_units ?? []

  task.raw_discovered_count = units.reduce((sum, unit) => sum + unit.raw_discovered_count, 0)
  // 任务【内部】去重 + AI 相关性判断；与 Dashboard 的全局口径不同
  task.deduplicated_count = Math.round(task.raw_discovered_count * DEDUPE_RATE)
  task.relevant_count = Math.round(task.raw_discovered_count * RELEVANT_RATE)
  task.queries_executed = units.filter((unit) => unit.status === 'completed').length
  task.search_results_count = task.raw_discovered_count
  task.valid_domains_count = task.deduplicated_count
  task.new_enterprises_count = task.relevant_count
  task.duplicate_enterprises_count = Math.max(
    task.valid_domains_count - task.new_enterprises_count,
    0
  )

  task.channel_snapshots.forEach((snapshot) => {
    snapshot.raw_discovered_count = units
      .filter((unit) => unit.channel === snapshot.channel)
      .reduce((sum, unit) => sum + unit.raw_discovered_count, 0)
  })
}

/* -------------------------------------------------------------------------- */
/* 演示数据                                                                     */
/* -------------------------------------------------------------------------- */

interface Seed {
  task_name: string
  profile_id: string
  strategy_id: string
  strategy_version: number
  status: TaskStatus
  channels: Array<{ channel: string; queries: string[]; countries: string[] }>
  raw: number
  day: number
  failure_reason?: string
}

function ch(
  channel: string,
  queries: string[],
  countries: string[]
): { channel: string; queries: string[]; countries: string[] } {
  return { channel, queries, countries }
}

const seeds: Seed[] = [
  {
    task_name: '德国工业控制柜 - 9 月第 3 批',
    profile_id: 'PRF-0001',
    strategy_id: 'STG-0001',
    strategy_version: 3,
    status: 'completed',
    channels: [
      ch('google', ['"industrial automation" manufacturer Germany', 'Automatisierungstechnik Hersteller', '"terminal block connector" supplier Germany'], ['DE', 'NL']),
      ch('company_site', ['site:.de Automatisierungstechnik terminal block connector'], ['DE']),
      ch('b2b', ['europages industrial automation manufacturer Germany'], ['DE', 'NL'])
    ],
    raw: 486,
    day: 22
  },
  {
    task_name: '意大利充电桩制造商 - 首轮',
    profile_id: 'PRF-0002',
    strategy_id: 'STG-0002',
    strategy_version: 2,
    status: 'completed',
    channels: [
      ch('google', ['"energy storage" manufacturer Italy', 'automazione industriale produttore'], ['IT', 'ES']),
      ch('company_site', ['site:.it automazione industriale power connector'], ['IT'])
    ],
    raw: 312,
    day: 21
  },
  {
    task_name: '印度 PCBA 加工厂 - TradeIndia 专项',
    profile_id: 'PRF-0004',
    strategy_id: 'STG-0004',
    strategy_version: 4,
    status: 'running',
    channels: [
      ch('tradeindia', ['tradeindia pin header buyer', 'tradeindia PCB assembly manufacturer'], ['IN']),
      ch('google', ['"PCB assembly" manufacturer India'], ['IN']),
      ch('b2b', ['kompass pin header supplier'], ['IN'])
    ],
    raw: 208,
    day: 23
  },
  {
    task_name: '土耳其安防设备厂 - 9 月',
    profile_id: 'PRF-0006',
    strategy_id: 'STG-0006',
    strategy_version: 1,
    status: 'failed',
    channels: [
      ch('google', ['"security surveillance" manufacturer Turkey'], ['TR', 'AE']),
      ch('b2b', ['europages security surveillance manufacturer Turkey'], ['TR'])
    ],
    raw: 0,
    day: 20,
    failure_reason: '渠道请求超时：Google 搜索连续 3 次返回 429，已达当日配额上限'
  },
  {
    task_name: '德国工业控制柜 - 补充批次',
    profile_id: 'PRF-0009',
    strategy_id: 'STG-0009',
    strategy_version: 2,
    status: 'pending',
    channels: [
      ch('google', ['"control cabinet" connector manufacturer Germany', 'Schaltschrank Hersteller Deutschland'], ['DE', 'PL']),
      ch('company_site', ['site:.de Schaltschrank Klemmenleiste'], ['DE']),
      ch('tradeindia', ['tradeindia terminal connector manufacturer'], ['IN']),
      ch('b2b', ['europages control cabinet Germany'], ['DE', 'PL'])
    ],
    raw: 0,
    day: 23
  },
  {
    task_name: '美国系统集成商 - 暂停中',
    profile_id: 'PRF-0005',
    strategy_id: 'STG-0005',
    strategy_version: 2,
    status: 'pending',
    channels: [
      ch('google', ['"system integrator" industrial automation United States'], ['US', 'CA']),
      ch('company_site', ['site:.com industrial automation system integrator'], ['US'])
    ],
    raw: 96,
    day: 19
  },
  {
    task_name: '法国医疗设备整机厂 - 试跑',
    profile_id: 'PRF-0003',
    strategy_id: 'STG-0003',
    strategy_version: 1,
    status: 'completed',
    channels: [ch('google', ['"medical imaging equipment" manufacturer France'], ['FR'])],
    raw: 128,
    day: 18
  },
  {
    task_name: '波兰储能集成商 - 首轮',
    profile_id: 'PRF-0008',
    strategy_id: 'STG-0008',
    strategy_version: 1,
    status: 'pending',
    channels: [
      ch('google', ['"battery energy storage system" Poland'], ['PL', 'DE']),
      ch('company_site', ['site:.pl automatyka przemysłowa'], ['PL'])
    ],
    raw: 0,
    day: 23
  },
  {
    task_name: '越南代工厂 - 9 月批次',
    profile_id: 'PRF-0007',
    strategy_id: 'STG-0007',
    strategy_version: 3,
    status: 'completed',
    channels: [
      ch('google', ['"consumer electronics" EMS Vietnam', 'tự động hóa công nghiệp nhà sản xuất'], ['VN', 'TH']),
      ch('b2b', ['europages EMS provider Vietnam'], ['VN'])
    ],
    raw: 254,
    day: 17
  },
  {
    task_name: '印度 PCBA - 二期专项',
    profile_id: 'PRF-0012',
    strategy_id: 'STG-0012',
    strategy_version: 5,
    status: 'failed',
    channels: [ch('tradeindia', ['tradeindia FFC FPC connector buyer'], ['IN'])],
    raw: 41,
    day: 16,
    failure_reason: 'TradeIndia 页面结构变更，解析器未能提取企业列表'
  },
  {
    task_name: '德国工业控制柜 - 8 月末批次',
    profile_id: 'PRF-0001',
    strategy_id: 'STG-0001',
    strategy_version: 2,
    status: 'completed',
    channels: [
      ch('google', ['"industrial automation" manufacturer Germany'], ['DE']),
      ch('b2b', ['kompass terminal block connector supplier'], ['DE'])
    ],
    raw: 398,
    day: 15
  },
  {
    task_name: '意大利充电桩 - 二期',
    profile_id: 'PRF-0010',
    strategy_id: 'STG-0010',
    strategy_version: 1,
    status: 'completed',
    channels: [ch('google', ['"EV charging station" manufacturer Italy'], ['IT'])],
    raw: 176,
    day: 14
  },
  {
    task_name: '美国自动化 - 高配额批次',
    profile_id: 'PRF-0014',
    strategy_id: 'STG-0014',
    strategy_version: 2,
    status: 'completed',
    channels: [
      ch('google', ['"industrial automation" manufacturer United States'], ['US']),
      ch('company_site', ['site:.com control cabinet manufacturer'], ['US']),
      ch('b2b', ['europages industrial automation United States'], ['US'])
    ],
    raw: 522,
    day: 13
  },
  {
    task_name: '法国医疗 - 二期',
    profile_id: 'PRF-0011',
    strategy_id: 'STG-0011',
    strategy_version: 2,
    status: 'pending',
    channels: [ch('google', ['"medical device" manufacturer France Spain'], ['FR', 'ES'])],
    raw: 64,
    day: 12
  },
  {
    task_name: '土耳其安防 - 重试批次',
    profile_id: 'PRF-0006',
    strategy_id: 'STG-0006',
    strategy_version: 1,
    status: 'completed',
    channels: [ch('google', ['"security camera" manufacturer Turkey'], ['TR'])],
    raw: 142,
    day: 11
  },
  {
    task_name: '德国工业控制柜 - 试运行',
    profile_id: 'PRF-0013',
    strategy_id: 'STG-0013',
    strategy_version: 1,
    status: 'completed',
    channels: [ch('google', ['"control cabinet" Germany'], ['DE'])],
    raw: 88,
    day: 10
  },
  {
    task_name: '印度 PCBA - 8 月批次',
    profile_id: 'PRF-0004',
    strategy_id: 'STG-0004',
    strategy_version: 3,
    status: 'completed',
    channels: [
      ch('tradeindia', ['tradeindia PCB assembly buyer'], ['IN']),
      ch('google', ['"PCB assembly" supplier India'], ['IN'])
    ],
    raw: 366,
    day: 9
  },
  {
    task_name: '越南代工厂 - 试跑',
    profile_id: 'PRF-0007',
    strategy_id: 'STG-0007',
    strategy_version: 2,
    status: 'failed',
    channels: [ch('company_site', ['site:.vn EMS provider'], ['VN'])],
    raw: 12,
    day: 8,
    failure_reason: '目标站点大面积返回 403，疑似触发反爬策略'
  }
]

function buildChannelSnapshots(seed: Seed, raw: number): TaskChannelSnapshot[] {
  const totalQueries = seed.channels.reduce((sum, item) => sum + item.queries.length, 0)
  return seed.channels.map((item) => ({
    channel: item.channel,
    queries: item.queries,
    target_countries: item.countries,
    raw_discovered_count: totalQueries
      ? Math.round((raw * item.queries.length) / totalQueries)
      : 0
  }))
}

/**
 * 按任务状态决定有多少执行单元已完成：
 *   completed → 全部完成
 *   running / paused → 完成一部分，剩余 pending（体现「继续执行」而非重跑）
 *   failed → 前面完成，最后一个失败
 *   pending → 全部未执行
 */
function applySeedUnits(task: AcquisitionTask, status: TaskStatus, targetRaw: number): void {
  const units = task.query_units ?? []
  if (!units.length) return

  let completedCount = 0
  if (status === 'completed') completedCount = units.length
  else if (status === 'running') {
    completedCount = Math.max(1, Math.floor(units.length * 0.6))
  } else if (status === 'failed') completedCount = Math.max(0, units.length - 1)

  const perUnit = completedCount ? Math.round(targetRaw / completedCount) : 0

  units.forEach((unit, index) => {
    if (index < completedCount) {
      unit.status = 'completed'
      unit.raw_discovered_count = perUnit
      unit.finished_at = task.started_at
    } else if (status === 'failed' && index === units.length - 1) {
      unit.status = 'failed'
      unit.failure_reason = task.failure_reason
    }
  })

  syncAggregates(task)
}

const dataset: AcquisitionTask[] = seeds.map((seed, index) => {
  const finished = seed.status === 'completed'
  const raw = seed.raw
  const countries = Array.from(new Set(seed.channels.flatMap((item) => item.countries)))
  const snapshots = buildChannelSnapshots(seed, raw)
  const task: AcquisitionTask = {
    id: `TSK-${String(index + 1).padStart(4, '0')}`,
    task_name: seed.task_name,
    profile_id: seed.profile_id,
    strategy_id: seed.strategy_id,
    strategy_code: seed.strategy_id,
    strategy_version: seed.strategy_version,
    profile_name: '',
    status: seed.status,
    max_queries: 3,
    results_per_query: 10,
    enterprise_target: 30,
    queries_executed: 0,
    search_results_count: 0,
    valid_domains_count: 0,
    new_enterprises_count: 0,
    duplicate_enterprises_count: 0,
    channel_snapshots: snapshots,
    query_count: seed.channels.reduce((sum, item) => sum + item.queries.length, 0),
    target_countries: countries,
    raw_discovered_count: 0,
    deduplicated_count: 0,
    relevant_count: 0,
    query_units: buildUnits(snapshots),
    failure_reason: seed.failure_reason,
    created_at: `2026-09-${String(seed.day).padStart(2, '0')} 08:10:00`,
    started_at: seed.status === 'pending' ? undefined : `2026-09-${String(seed.day).padStart(2, '0')} 08:15:00`,
    finished_at: finished ? `2026-09-${String(seed.day).padStart(2, '0')} 09:02:00` : undefined,
    updated_at: `2026-09-${String(seed.day).padStart(2, '0')} 09:05:00`
  }

  applySeedUnits(task, seed.status, raw)
  return task
})

/** 模拟 JOIN CustomerProfile：profile_name 为 derived 只读字段，实时取最新值 */
function withProfileMeta(task: AcquisitionTask): AcquisitionTask {
  const meta = getProfileMetaMock(task.profile_id)
  return { ...task, profile_name: meta?.profile_name ?? task.profile_name }
}

function nextId(): string {
  return `TSK-${String(dataset.length + 1).padStart(4, '0')}`
}

/* -------------------------------------------------------------------------- */
/* 执行模拟                                                                     */
/* -------------------------------------------------------------------------- */

/** 每个任务的推进定时器，用于暂停时清理 */
const timers = new Map<string, number[]>()

function clearTimers(id: string): void {
  timers.get(id)?.forEach((timer) => window.clearTimeout(timer))
  timers.delete(id)
}

/**
 * 推进执行：每个 tick 完成一个 pending 执行单元
 *
 * 关键语义（业务确认）：
 *   - 已完成单元的结果保留，暂停后继续只跑剩余 pending 单元，不整体重跑
 *   - 任务聚合值由已完成单元回算，因此继续执行时数字只增不退
 *   - P0 不做搜索结果页级断点，单元内部重跑靠企业全局去重兜底
 */
function runTask(task: AcquisitionTask): void {
  clearTimers(task.id)

  const handles: number[] = []
  const pendingCount = (task.query_units ?? []).filter((unit) => unit.status !== 'completed').length

  for (let step = 1; step <= pendingCount; step += 1) {
    const handle = window.setTimeout(() => {
      const current = dataset.find((item) => item.id === task.id)
      if (!current || current.status !== 'running') return

      const next = (current.query_units ?? []).find((unit) => unit.status !== 'completed')
      if (next) {
        next.status = 'completed'
        next.failure_reason = undefined
        next.started_at = next.started_at ?? now()
        next.finished_at = now()
        next.raw_discovered_count = expectedRawPerQuery(step)
      }

      syncAggregates(current)
      current.updated_at = now()

      const remaining = (current.query_units ?? []).some((unit) => unit.status !== 'completed')
      if (!remaining) {
        current.status = 'completed'
        current.finished_at = now()
        clearTimers(current.id)
      }
    }, TICK_INTERVAL * step)
    handles.push(handle)
  }

  timers.set(task.id, handles)
}

/**
 * 并发锁：同一 strategy_id + strategy_version 同时只允许一个任务占用执行资源
 *
 * running → 占用
 * completed / failed → 释放
 */
function findBusyTask(task: AcquisitionTask): AcquisitionTask | undefined {
  return dataset.find(
    (item) =>
      item.id !== task.id &&
      item.strategy_id === task.strategy_id &&
      item.strategy_version === task.strategy_version &&
      item.status === 'running'
  )
}

function assertStrategyIdle(task: AcquisitionTask): ApiError | undefined {
  const busy = findBusyTask(task)
  if (!busy) return undefined
  return new ApiError(
    `${TASK_STRATEGY_BUSY_HINT}（${busy.id} · ${busy.task_name}）`,
    409,
    TASK_STRATEGY_BUSY
  )
}

/* -------------------------------------------------------------------------- */
/* 服务方法                                                                     */
/* -------------------------------------------------------------------------- */

/**
 * 同步查询任务元信息
 * 供企业发现来源 JOIN AcquisitionTask 使用，真实环境由后端 join 返回。
 */
export function getTaskMetaMock(
  id: string
):
  | { task_name: string; strategy_id: string; strategy_version: number; profile_id: string }
  | undefined {
  const target = dataset.find((item) => item.id === id)
  if (!target) return undefined
  return {
    task_name: target.task_name,
    strategy_id: target.strategy_id,
    strategy_version: target.strategy_version,
    // 企业相关性是「企业 × 画像」的判断，列表按 task_id 查看时需据此推导画像语境
    profile_id: target.profile_id
  }
}

/** 列表：服务端筛选 + 分页语义 */
export function listTasksMock(query: TaskQuery): Promise<PageResult<AcquisitionTask>> {
  const nameKeyword = query.task_name?.trim().toLowerCase()
  const profileKeyword = query.profile_name?.trim().toLowerCase()

  const filtered = dataset.map(withProfileMeta).filter((item) => {
    if (nameKeyword && !item.task_name.toLowerCase().includes(nameKeyword)) return false
    if (profileKeyword && !item.profile_name.toLowerCase().includes(profileKeyword)) return false
    if (query.strategy_id && item.strategy_id !== query.strategy_id) return false
    if (query.status && item.status !== query.status) return false
    return true
  })

  const start = (query.page - 1) * query.page_size
  return delay({
    list: filtered.slice(start, start + query.page_size),
    total: filtered.length,
    page: query.page,
    page_size: query.page_size
  })
}

/** 详情 */
export function getTaskMock(id: string): Promise<AcquisitionTask> {
  const target = dataset.find((item) => item.id === id)
  if (!target) return Promise.reject(new Error('获客任务不存在'))
  return delay(withProfileMeta(structuredClone(target)))
}

/**
 * 创建任务
 * 按 strategy_id 取策略快照，固化 strategy_version 与渠道 / Query，
 * 创建后为 pending，不自动执行。
 */
export async function createTaskMock(payload: TaskCreatePayload): Promise<AcquisitionTask> {
  const strategy = await getStrategyMock(payload.strategy_id)

  const enabledChannels = strategy.channel_strategies.filter(
    (channel) =>
      channel.enabled &&
      channel.queries.some((query) => query.enabled && query.query_text.trim().length > 0)
  )
  if (!enabledChannels.length) {
    return Promise.reject(new Error('该策略没有可执行的渠道或 Query，无法创建任务'))
  }
  if (strategy.status !== 'active') {
    return Promise.reject(new Error('仅启用状态的搜索策略可创建获客任务'))
  }
  if (strategy.profile_enabled === false) {
    return Promise.reject(new Error('上游客户画像已暂停，暂不能创建新的获客任务'))
  }

  const snapshots: TaskChannelSnapshot[] = enabledChannels.map((channel) => ({
    channel: channel.channel,
    queries: channel.queries
      .filter((query) => query.enabled && query.query_text.trim().length > 0)
      .map((query) => query.query_text),
    target_countries: channel.target_countries,
    raw_discovered_count: 0
  }))

  const created: AcquisitionTask = {
    id: nextId(),
    task_name: payload.task_name,
    profile_id: strategy.profile_id,
    strategy_id: payload.strategy_id,
    strategy_code: strategy.code,
    strategy_version: strategy.version,
    profile_name: '',
    status: 'pending',
    max_queries: payload.max_queries,
    results_per_query: payload.results_per_query,
    enterprise_target: payload.enterprise_target,
    queries_executed: 0,
    search_results_count: 0,
    valid_domains_count: 0,
    new_enterprises_count: 0,
    duplicate_enterprises_count: 0,
    channel_snapshots: snapshots,
    query_count: snapshots.reduce((sum, item) => sum + item.queries.length, 0),
    target_countries: Array.from(new Set(snapshots.flatMap((item) => item.target_countries))),
    raw_discovered_count: 0,
    deduplicated_count: 0,
    relevant_count: 0,
    query_units: buildUnits(snapshots),
    created_at: now(),
    updated_at: now()
  }

  dataset.unshift(created)
  return delay(withProfileMeta(structuredClone(created)))
}

/**
 * 启动：pending → running。
 */
export function startTaskMock(id: string): Promise<AcquisitionTask> {
  const target = dataset.find((item) => item.id === id)
  if (!target) return Promise.reject(new Error('获客任务不存在'))
  if (target.status === 'running') return Promise.reject(new Error('任务已在执行中'))
  if (target.status === 'completed') return Promise.reject(new Error('任务已完成，无需重复执行'))
  if (target.status === 'failed') return Promise.reject(new Error('失败任务不可重复执行'))

  // 同一策略版本的并发占用检查：后端必须独立保证，不能只依赖前端按钮
  const conflict = assertStrategyIdle(target)
  if (conflict) return Promise.reject(conflict)

  target.status = 'running'
  target.started_at = target.started_at ?? now()
  target.finished_at = undefined
  target.failure_reason = undefined
  target.updated_at = now()
  runTask(target)

  return delay(withProfileMeta(structuredClone(target)))
}

/** 重试：失败任务重新执行，结果数字清零重跑 */
export function retryTaskMock(id: string): Promise<AcquisitionTask> {
  const target = dataset.find((item) => item.id === id)
  if (!target) return Promise.reject(new Error('获客任务不存在'))
  if (target.status !== 'failed') return Promise.reject(new Error('仅失败的任务可以重试'))

  const conflict = assertStrategyIdle(target)
  if (conflict) return Promise.reject(conflict)

  // 重试是显式的「重新执行整个任务」，所有执行单元回到 pending
  target.status = 'running'
  target.failure_reason = undefined
  target.query_units?.forEach((unit) => {
    unit.status = 'pending'
    unit.raw_discovered_count = 0
    unit.started_at = undefined
    unit.finished_at = undefined
    unit.failure_reason = undefined
  })
  syncAggregates(target)
  target.started_at = now()
  target.finished_at = undefined
  target.updated_at = now()
  runTask(target)

  return delay(withProfileMeta(structuredClone(target)))
}

/** 顶部统计 */
export function getTaskStatsMock(): Promise<TaskStats> {
  return delay({
    total: dataset.length,
    pending: dataset.filter((item) => item.status === 'pending').length,
    running: dataset.filter((item) => item.status === 'running').length,
    completed: dataset.filter((item) => item.status === 'completed').length,
    failed: dataset.filter((item) => item.status === 'failed').length
  })
}
