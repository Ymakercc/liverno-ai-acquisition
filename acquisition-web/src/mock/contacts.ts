/**
 * 联系人 Mock 服务
 * CLAUDE.md 8.3：Mock 统一放 src/mock，禁止写在 Vue 页面中。
 *
 * 数据模型要点：
 *   contacts       —— 联系人，归属 enterprise_id（无 profile_id）
 *   contactSources —— 来源记录，同一联系人可多条
 *   tasks          —— 联系人获取任务，企业维度，自动创建
 *
 * 去重语义：同一企业内 normalized_email 一致即合并为同一 Contact；
 * 无邮箱时按 normalized_linkedin_url 合并；仅姓名/职位相似不合并。
 */
import { getEnterpriseMetaMock, hasRelevantAnalysisMock } from './companies'
import { getProfileMetaMock } from './profiles'
import type { PageResult } from '@/types/common'
import type {
  Contact,
  ContactAcquisitionTask,
  ContactQuery,
  ContactSource,
  ContactSourceType,
  ContactStats,
  ContactTaskQuery,
  EmailVerificationStatus
} from '@/types/contact'

const LATENCY = 300
const ACQUIRE_MIN = 900
const ACQUIRE_MAX = 1600

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

/** 去重键：邮箱归一化 */
function normalizeEmail(email: string | undefined): string | undefined {
  return email?.trim().toLowerCase() || undefined
}

/** 去重键：LinkedIn URL 归一化（去协议、去 www、去尾斜杠、去查询串） */
function normalizeLinkedin(url: string | undefined): string | undefined {
  if (!url) return undefined
  return url
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '')
    .split('?')[0]
    .replace(/\/+$/, '')
}

/* -------------------------------------------------------------------------- */
/* 演示数据                                                                     */
/* -------------------------------------------------------------------------- */

interface ContactSeed {
  enterprise_id: string
  full_name: string
  title: string
  department?: string
  email?: string
  linkedin_url?: string
  email_status: EmailVerificationStatus
  email_detail?: string
  /** 来源可多条，体现「同一联系人被多个来源发现」 */
  sources: Array<[ContactSourceType, string | undefined]>
  day: number
}

const contactSeeds: ContactSeed[] = [
  // ---- ENT-00001 Rittal：5 人，含一个多来源合并的联系人 ----
  {
    enterprise_id: 'ENT-00001',
    full_name: 'Markus Weber',
    title: 'Purchasing Manager',
    department: 'Procurement',
    email: 'm.weber@rittal.com',
    linkedin_url: 'https://www.linkedin.com/in/markus-weber-rittal',
    email_status: 'valid',
    // Apollo 与官网各发现一次，normalized_email 一致 → 合并为同一个 Contact
    sources: [
      ['apollo', 'https://app.apollo.io/#/people/markus-weber'],
      ['website', 'https://www.rittal.com/de/contact/purchasing']
    ],
    day: 22
  },
  {
    enterprise_id: 'ENT-00001',
    full_name: 'Sabine Hoffmann',
    title: 'Senior Hardware Engineer',
    department: 'R&D',
    email: 's.hoffmann@rittal.com',
    email_status: 'valid',
    sources: [['apollo', undefined]],
    day: 22
  },
  {
    enterprise_id: 'ENT-00001',
    full_name: 'Thomas Krüger',
    title: 'Supply Chain Manager',
    department: 'Supply Chain',
    email: 't.krueger@rittal.com',
    email_status: 'catch_all',
    email_detail: '域名为 catch-all 配置，无法确认该邮箱真实存在',
    sources: [['apollo', undefined]],
    day: 22
  },
  {
    enterprise_id: 'ENT-00001',
    full_name: 'Julia Becker',
    title: 'Purchasing Engineer',
    department: 'Procurement',
    email: 'j.becker@rittal.com',
    email_status: 'invalid',
    email_detail: 'SMTP 校验返回 550，邮箱不存在',
    sources: [['website', 'https://www.rittal.com/de/imprint']],
    day: 22
  },
  {
    enterprise_id: 'ENT-00001',
    full_name: 'Andreas Lang',
    title: 'CTO',
    department: 'Management',
    linkedin_url: 'https://www.linkedin.com/in/andreas-lang-rittal',
    email_status: 'pending',
    // 无邮箱，靠 LinkedIn 归一化去重
    sources: [['b2b', 'https://www.europages.de/rittal'], ['other', undefined]],
    day: 22
  },

  // ---- ENT-00002 Phoenix Contact ----
  {
    enterprise_id: 'ENT-00002',
    full_name: 'Klaus Richter',
    title: 'Head of Procurement',
    department: 'Procurement',
    email: 'k.richter@phoenixcontact.com',
    email_status: 'valid',
    sources: [['apollo', undefined], ['b2b', 'https://www.kompass.com/phoenixcontact']],
    day: 22
  },
  {
    enterprise_id: 'ENT-00002',
    full_name: 'Nina Schäfer',
    title: 'R&D Engineer',
    department: 'R&D',
    email: 'n.schaefer@phoenixcontact.com',
    email_status: 'unknown',
    email_detail: '目标邮件服务器超时，未能完成验证',
    sources: [['apollo', undefined]],
    day: 22
  },

  // ---- ENT-00003 Eldon ----
  {
    enterprise_id: 'ENT-00003',
    full_name: 'Peter Vogel',
    title: 'Purchasing Manager',
    department: 'Procurement',
    email: 'p.vogel@eldon.com',
    email_status: 'valid',
    sources: [['website', 'https://www.eldon.com/contact']],
    day: 22
  },
  {
    enterprise_id: 'ENT-00003',
    full_name: 'Martina Frei',
    title: 'Product Manager',
    email: 'm.frei@eldon.com',
    email_status: 'invalid',
    email_detail: '邮箱域名 MX 记录不可达',
    sources: [['apollo', undefined]],
    day: 22
  },

  // ---- ENT-00005 Alfen ----
  {
    enterprise_id: 'ENT-00005',
    full_name: 'Jeroen van Dijk',
    title: 'Purchasing Engineer',
    department: 'Procurement',
    email: 'j.vandijk@alfen.com',
    email_status: 'valid',
    sources: [['apollo', undefined], ['website', 'https://alfen.com/en/contact']],
    day: 21
  },
  {
    enterprise_id: 'ENT-00005',
    full_name: 'Lotte Jansen',
    title: 'Hardware Engineer',
    department: 'Engineering',
    email: 'l.jansen@alfen.com',
    email_status: 'valid',
    sources: [['apollo', undefined]],
    day: 21
  },
  {
    enterprise_id: 'ENT-00005',
    full_name: 'Bram de Vries',
    title: 'General Manager',
    linkedin_url: 'https://linkedin.com/in/bram-de-vries/',
    email_status: 'pending',
    sources: [['other', undefined]],
    day: 21
  },

  // ---- ENT-00006 Scame ----
  {
    enterprise_id: 'ENT-00006',
    full_name: 'Giulia Rossi',
    title: 'Responsabile Acquisti',
    department: 'Acquisti',
    email: 'g.rossi@scame.com',
    email_status: 'catch_all',
    email_detail: '域名为 catch-all 配置，P0 不允许进入自动营销',
    sources: [['website', 'https://www.scame.com/it/contatti']],
    day: 21
  },
  {
    enterprise_id: 'ENT-00006',
    full_name: 'Marco Bianchi',
    title: 'R&D Engineer',
    email: 'm.bianchi@scame.com',
    email_status: 'valid',
    sources: [['apollo', undefined]],
    day: 21
  },

  // ---- ENT-00008 Siemens Healthineers ----
  {
    enterprise_id: 'ENT-00008',
    full_name: 'Frank Neumann',
    title: 'Strategic Sourcing Manager',
    department: 'Sourcing',
    email: 'frank.neumann@siemens-healthineers.com',
    email_status: 'valid',
    sources: [['apollo', undefined]],
    day: 18
  },
  {
    enterprise_id: 'ENT-00008',
    full_name: 'Petra Wolf',
    title: 'Hardware Engineer',
    email: 'petra.wolf@siemens-healthineers.com',
    email_status: 'unknown',
    email_detail: '企业邮箱启用反垃圾策略，验证结果不确定',
    sources: [['apollo', undefined], ['website', undefined]],
    day: 18
  },

  // ---- ENT-00010 Bharat Circuits ----
  {
    enterprise_id: 'ENT-00010',
    full_name: 'Rajesh Kumar',
    title: 'Purchasing Manager',
    department: 'Purchase',
    email: 'rajesh.kumar@bharatcircuits.in',
    email_status: 'valid',
    sources: [['b2b', 'https://www.tradeindia.com/bharatcircuits'], ['apollo', undefined]],
    day: 23
  },
  {
    enterprise_id: 'ENT-00010',
    full_name: 'Anita Sharma',
    title: 'Supply Chain Executive',
    email: 'anita.sharma@bharatcircuits.in',
    email_status: 'valid',
    sources: [['apollo', undefined]],
    day: 23
  },
  {
    enterprise_id: 'ENT-00010',
    full_name: 'Vikram Singh',
    title: 'Production Head',
    email: 'vikram.singh@bharatcircuits.in',
    email_status: 'invalid',
    email_detail: 'SMTP 校验返回 550，邮箱不存在',
    sources: [['b2b', undefined]],
    day: 23
  },

  // ---- ENT-00013 Rockwell ----
  {
    enterprise_id: 'ENT-00013',
    full_name: 'Michael Brown',
    title: 'Category Manager - Components',
    department: 'Procurement',
    email: 'michael.brown@rockwellautomation.com',
    email_status: 'valid',
    sources: [['apollo', undefined]],
    day: 13
  },
  {
    enterprise_id: 'ENT-00013',
    full_name: 'Jennifer Davis',
    title: 'Hardware Engineer',
    email: 'jennifer.davis@rockwellautomation.com',
    email_status: 'catch_all',
    email_detail: '域名为 catch-all 配置',
    sources: [['apollo', undefined], ['website', undefined]],
    day: 13
  },

  // ---- ENT-00014 Midwest Control Systems ----
  {
    enterprise_id: 'ENT-00014',
    full_name: 'Robert Miller',
    title: 'Owner / Purchasing',
    email: 'rob@midwestcontrols.com',
    email_status: 'valid',
    sources: [['website', 'https://midwestcontrols.com/about']],
    day: 13
  },

  // ---- ENT-00016 Vestel ----
  {
    enterprise_id: 'ENT-00016',
    full_name: 'Emre Yılmaz',
    title: 'Satın Alma Müdürü',
    department: 'Satın Alma',
    email: 'emre.yilmaz@vestelsavunma.com',
    email_status: 'pending',
    sources: [['apollo', undefined]],
    day: 11
  },

  // ---- ENT-00018 VinFast Electronics ----
  {
    enterprise_id: 'ENT-00018',
    full_name: 'Nguyen Van An',
    title: 'Procurement Lead',
    department: 'Procurement',
    email: 'an.nguyen@vinfast-electronics.vn',
    email_status: 'valid',
    sources: [['apollo', undefined], ['b2b', undefined]],
    day: 17
  },
  {
    enterprise_id: 'ENT-00018',
    full_name: 'Tran Thi Mai',
    title: 'Supply Chain Manager',
    email: 'mai.tran@vinfast-electronics.vn',
    email_status: 'unknown',
    sources: [['apollo', undefined]],
    day: 17
  }
]

/* -------------------------------------------------------------------------- */
/* 建模：联系人 / 来源 分开存储                                                  */
/* -------------------------------------------------------------------------- */

let contactSeedId = 0
let sourceSeedId = 0

const contactSources: ContactSource[] = []

const contacts: Contact[] = contactSeeds.map((seed) => {
  contactSeedId += 1
  const id = `CTC-${String(contactSeedId).padStart(5, '0')}`

  seed.sources.forEach(([source, url], index) => {
    sourceSeedId += 1
    contactSources.push({
      id: `CTS-${String(sourceSeedId).padStart(5, '0')}`,
      contact_id: id,
      source,
      source_url: url,
      discovered_at: `2026-09-${String(seed.day).padStart(2, '0')} 1${index}:15:00`
    })
  })

  return {
    id,
    enterprise_id: seed.enterprise_id,
    enterprise_name: '',
    full_name: seed.full_name,
    title: seed.title,
    department: seed.department,
    email: seed.email,
    normalized_email: normalizeEmail(seed.email),
    linkedin_url: seed.linkedin_url,
    normalized_linkedin_url: normalizeLinkedin(seed.linkedin_url),
    email_verification: {
      status: seed.email_status,
      verified_at:
        seed.email_status === 'pending'
          ? undefined
          : `2026-09-${String(seed.day).padStart(2, '0')} 12:05:00`,
      detail: seed.email_detail
    },
    source_types: [],
    created_at: `2026-09-${String(seed.day).padStart(2, '0')} 10:40:00`,
    updated_at: `2026-09-${String(seed.day).padStart(2, '0')} 12:05:00`
  }
})

/* ---------------- 联系人获取任务：企业维度，自动创建 ---------------- */

interface TaskSeed {
  enterprise_id: string
  primary_profile_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  target_roles: string[]
  failure_reason?: string
  day: number
}

const taskSeeds: TaskSeed[] = [
  { enterprise_id: 'ENT-00001', primary_profile_id: 'PRF-0001', status: 'completed', target_roles: ['purchasing_manager', 'rd_engineer'], day: 22 },
  { enterprise_id: 'ENT-00002', primary_profile_id: 'PRF-0001', status: 'completed', target_roles: ['purchasing_manager', 'rd_engineer'], day: 22 },
  { enterprise_id: 'ENT-00003', primary_profile_id: 'PRF-0001', status: 'completed', target_roles: ['purchasing_manager', 'rd_engineer'], day: 22 },
  { enterprise_id: 'ENT-00005', primary_profile_id: 'PRF-0002', status: 'completed', target_roles: ['purchasing_engineer', 'hardware_engineer'], day: 21 },
  { enterprise_id: 'ENT-00006', primary_profile_id: 'PRF-0002', status: 'completed', target_roles: ['purchasing_engineer', 'hardware_engineer'], day: 21 },
  { enterprise_id: 'ENT-00008', primary_profile_id: 'PRF-0003', status: 'completed', target_roles: ['rd_engineer', 'cto'], day: 18 },
  { enterprise_id: 'ENT-00010', primary_profile_id: 'PRF-0004', status: 'completed', target_roles: ['purchasing_manager', 'supply_chain_manager'], day: 23 },
  { enterprise_id: 'ENT-00013', primary_profile_id: 'PRF-0014', status: 'completed', target_roles: ['purchasing_engineer'], day: 13 },
  { enterprise_id: 'ENT-00014', primary_profile_id: 'PRF-0014', status: 'completed', target_roles: ['purchasing_engineer'], day: 13 },
  { enterprise_id: 'ENT-00016', primary_profile_id: 'PRF-0006', status: 'completed', target_roles: ['purchasing_manager'], day: 11 },
  { enterprise_id: 'ENT-00018', primary_profile_id: 'PRF-0007', status: 'completed', target_roles: ['supply_chain_manager', 'purchasing_engineer'], day: 17 },
  // 失败：可重新获取
  { enterprise_id: 'ENT-00021', primary_profile_id: 'PRF-0006', status: 'failed', target_roles: ['purchasing_manager'], failure_reason: 'Apollo 返回 402：当月联系人补全配额已用尽', day: 20 },
  { enterprise_id: 'ENT-00012', primary_profile_id: 'PRF-0004', status: 'failed', target_roles: ['purchasing_manager'], failure_reason: '企业官网无任何可解析的联系方式，Apollo 亦无匹配记录', day: 23 },
  // 待执行 / 执行中
  { enterprise_id: 'ENT-00009', primary_profile_id: 'PRF-0003', status: 'pending', target_roles: ['rd_engineer', 'cto'], day: 18 },
  { enterprise_id: 'ENT-00011', primary_profile_id: 'PRF-0004', status: 'running', target_roles: ['purchasing_manager'], day: 23 }
]

let taskSeedId = 0
const tasks: ContactAcquisitionTask[] = taskSeeds.map((seed) => {
  taskSeedId += 1
  const found = contacts.filter((item) => item.enterprise_id === seed.enterprise_id).length
  return {
    id: `CAT-${String(taskSeedId).padStart(5, '0')}`,
    enterprise_id: seed.enterprise_id,
    enterprise_name: '',
    primary_profile_id: seed.primary_profile_id,
    primary_analysis_id: `EPA-${String(taskSeedId).padStart(5, '0')}`,
    target_roles: seed.target_roles,
    status: seed.status,
    found_count: seed.status === 'completed' ? found : 0,
    failure_reason: seed.failure_reason,
    created_at: `2026-09-${String(seed.day).padStart(2, '0')} 10:00:00`,
    started_at: seed.status === 'pending' ? undefined : `2026-09-${String(seed.day).padStart(2, '0')} 10:05:00`,
    finished_at:
      seed.status === 'completed' || seed.status === 'failed'
        ? `2026-09-${String(seed.day).padStart(2, '0')} 10:35:00`
        : undefined
  }
})

/* -------------------------------------------------------------------------- */
/* 组装与派生                                                                   */
/* -------------------------------------------------------------------------- */

function sourcesOf(contactId: string): ContactSource[] {
  return contactSources.filter((item) => item.contact_id === contactId)
}

/** 模拟 JOIN Enterprise：enterprise_name / domain 为 derived 只读字段 */
function withContactMeta(contact: Contact): Contact {
  const meta = getEnterpriseMetaMock(contact.enterprise_id)
  const list = sourcesOf(contact.id)
  return {
    ...contact,
    enterprise_name: meta?.company_name ?? contact.enterprise_id,
    enterprise_domain: meta?.domain,
    source_types: Array.from(new Set(list.map((item) => item.source))),
    sources: list
  }
}

function withTaskMeta(task: ContactAcquisitionTask): ContactAcquisitionTask {
  return {
    ...task,
    enterprise_name: getEnterpriseMetaMock(task.enterprise_id)?.company_name ?? task.enterprise_id,
    primary_profile_name: getProfileMetaMock(task.primary_profile_id)?.profile_name
  }
}

/**
 * 企业是否满足进入待开发客户池的条件（CLAUDE.md 9.3.1）：
 *   存在 relevant 分析 + 联系人获取完成 + 至少一个 valid 邮箱
 */
export function isDevelopmentReadyMock(enterpriseId: string): boolean {
  if (!hasRelevantAnalysisMock(enterpriseId)) return false
  const task = tasks.find((item) => item.enterprise_id === enterpriseId)
  if (task?.status !== 'completed') return false
  return contacts.some(
    (item) => item.enterprise_id === enterpriseId && item.email_verification.status === 'valid'
  )
}

/* -------------------------------------------------------------------------- */
/* 服务方法                                                                     */
/* -------------------------------------------------------------------------- */

/** 联系人列表：服务端筛选 + 分页语义 */
export function listContactsMock(query: ContactQuery): Promise<PageResult<Contact>> {
  const keyword = query.keyword?.trim().toLowerCase()
  const enterpriseKeyword = query.enterprise_name?.trim().toLowerCase()
  const titleKeyword = query.title?.trim().toLowerCase()

  const filtered = contacts.map(withContactMeta).filter((item) => {
    if (keyword) {
      const hit =
        item.full_name.toLowerCase().includes(keyword) ||
        (item.email?.toLowerCase().includes(keyword) ?? false)
      if (!hit) return false
    }
    if (query.enterprise_id && item.enterprise_id !== query.enterprise_id) return false
    if (enterpriseKeyword && !item.enterprise_name.toLowerCase().includes(enterpriseKeyword)) {
      return false
    }
    if (titleKeyword && !(item.title?.toLowerCase().includes(titleKeyword) ?? false)) return false
    if (query.email_status && item.email_verification.status !== query.email_status) return false
    if (query.source && !item.source_types.includes(query.source)) return false
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

/** 联系人获取任务列表 */
export function listContactTasksMock(query: ContactTaskQuery): Promise<ContactAcquisitionTask[]> {
  const filtered = tasks.filter((item) => {
    if (query.enterprise_id && item.enterprise_id !== query.enterprise_id) return false
    if (query.status && item.status !== query.status) return false
    return true
  })
  return delay(filtered.map(withTaskMeta))
}

/**
 * 重新获取联系人
 * 仅失败任务可重试；成功后按去重规则写入联系人（相同 normalized_email 合并来源，不新建）。
 */
export function retryContactTaskMock(id: string): Promise<ContactAcquisitionTask> {
  const task = tasks.find((item) => item.id === id)
  if (!task) return Promise.reject(new Error('联系人获取任务不存在'))
  if (task.status !== 'failed') return Promise.reject(new Error('仅获取失败的任务可以重新获取'))

  const meta = getEnterpriseMetaMock(task.enterprise_id)
  const domain = meta?.domain ?? 'example.com'
  const candidates = [
    { full_name: 'Procurement Lead', title: 'Purchasing Manager', email: `purchasing@${domain}` },
    { full_name: 'Technical Contact', title: 'R&D Engineer', email: `engineering@${domain}` }
  ]

  candidates.forEach((candidate) => {
    const normalized = normalizeEmail(candidate.email)
    const existing = contacts.find(
      (item) => item.enterprise_id === task.enterprise_id && item.normalized_email === normalized
    )

    if (existing) {
      // 去重命中：不新建联系人，只追加一条来源
      sourceSeedId += 1
      contactSources.push({
        id: `CTS-${String(sourceSeedId).padStart(5, '0')}`,
        contact_id: existing.id,
        source: 'apollo',
        discovered_at: now()
      })
      existing.updated_at = now()
      return
    }

    contactSeedId += 1
    const contactId = `CTC-${String(contactSeedId).padStart(5, '0')}`
    contacts.unshift({
      id: contactId,
      enterprise_id: task.enterprise_id,
      enterprise_name: '',
      full_name: candidate.full_name,
      title: candidate.title,
      email: candidate.email,
      normalized_email: normalized,
      email_verification: { status: 'pending' },
      source_types: [],
      created_at: now(),
      updated_at: now()
    })
    sourceSeedId += 1
    contactSources.push({
      id: `CTS-${String(sourceSeedId).padStart(5, '0')}`,
      contact_id: contactId,
      source: 'apollo',
      discovered_at: now()
    })
  })

  task.status = 'completed'
  task.failure_reason = undefined
  task.found_count = contacts.filter((item) => item.enterprise_id === task.enterprise_id).length
  task.started_at = now()
  task.finished_at = now()

  return delay(withTaskMeta(task), ACQUIRE_MIN + Math.floor(Math.random() * (ACQUIRE_MAX - ACQUIRE_MIN)))
}

/**
 * 重新验证邮箱
 * 验证失败的联系人保留记录，只更新验证状态（CLAUDE.md 9.4）。
 */
export function verifyContactEmailMock(id: string): Promise<Contact> {
  const contact = contacts.find((item) => item.id === id)
  if (!contact) return Promise.reject(new Error('联系人不存在'))
  if (!contact.email) return Promise.reject(new Error('该联系人没有邮箱，无法验证'))

  // 确定性结果：避免同一联系人反复点击结果乱跳
  const seedNumber = Number(contact.id.replace(/\D/g, ''))
  const statuses: EmailVerificationStatus[] = ['valid', 'valid', 'catch_all', 'invalid', 'unknown']
  const status = statuses[seedNumber % statuses.length]

  contact.email_verification = {
    status,
    verified_at: now(),
    detail:
      status === 'valid'
        ? undefined
        : status === 'invalid'
          ? 'SMTP 校验返回 550，邮箱不存在'
          : status === 'catch_all'
            ? '域名为 catch-all 配置，无法确认该邮箱真实存在'
            : '目标邮件服务器无响应，验证结果不确定'
  }
  contact.updated_at = now()

  return delay(withContactMeta(contact), 600)
}

/** 顶部统计 */
export function getContactStatsMock(): Promise<ContactStats> {
  const enterpriseIds = Array.from(new Set(contacts.map((item) => item.enterprise_id)))
  return delay({
    total: contacts.length,
    valid: contacts.filter((item) => item.email_verification.status === 'valid').length,
    invalid: contacts.filter((item) => item.email_verification.status === 'invalid').length,
    pending: contacts.filter((item) => item.email_verification.status === 'pending').length,
    ready_enterprises: enterpriseIds.filter((id) => isDevelopmentReadyMock(id)).length
  })
}
