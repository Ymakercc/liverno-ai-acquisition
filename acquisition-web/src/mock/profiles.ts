/**
 * 客户画像 Mock 服务
 * CLAUDE.md 8.3：Mock 统一放 src/mock，禁止写在 Vue 页面中。
 *
 * 该 Mock 完整模拟服务端语义：筛选、分页、总数、单条查询、写入后返回最新实体。
 * 后端就绪后只需把 src/api/profile.ts 的开关切到真实请求，页面与类型均不需改动。
 */
import type { PageResult } from '@/types/common'
import type {
  CustomerProfile,
  ProfilePayload,
  ProfileQuery,
  ProfileStatusPayload
} from '@/types/profile'

/** 模拟网络延迟 */
const LATENCY = 300

function delay<T>(data: T): Promise<T> {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve(data), LATENCY)
  })
}

function isoAt(day: number, hour: number): string {
  const month = day > 9 ? '09' : '09'
  return `2026-${month}-${String(day).padStart(2, '0')} ${String(hour).padStart(2, '0')}:20:00`
}

/** 演示数据：覆盖不同行业、国家、优先级与启用状态，便于验证筛选与分页 */
const seeds: Array<Partial<CustomerProfile> & { profile_name: string }> = [
  {
    profile_name: '德国工业控制柜连接器采购商',
    target_industries: ['industrial_automation', 'connector_harness'],
    target_regions: ['western_europe'],
    target_countries: ['DE', 'NL'],
    company_types: ['oem', 'system_integrator'],
    company_size: '51-200',
    product_lines: ['terminal_connector', 'pcb_connector'],
    application_scenarios: ['industrial_cabinet', 'servo_drive'],
    required_signals: [
      '官网明确展示工业控制柜或配电柜产品',
      '有独立的采购或供应商合作页面',
      '产品页出现 connector / terminal block 等关键词'
    ],
    exclude_signals: ['纯电商零售网站', '已是我司现有客户', '网站无任何联系方式'],
    target_roles: ['purchasing_manager', 'rd_engineer'],
    daily_quota: 60,
    priority: 'high',
    is_enabled: true
  },
  {
    profile_name: '意大利新能源充电桩制造商',
    target_industries: ['energy_storage', 'automotive_electronics'],
    target_regions: ['western_europe'],
    target_countries: ['IT', 'ES'],
    company_types: ['oem', 'brand'],
    company_size: '201-500',
    product_lines: ['power_connector', 'waterproof_connector'],
    application_scenarios: ['ev_charger', 'energy_storage_system'],
    required_signals: ['官网有充电桩或储能柜产品线', '近一年有新品发布或展会信息'],
    exclude_signals: ['仅做充电运营服务、不生产硬件'],
    target_roles: ['purchasing_engineer', 'hardware_engineer'],
    daily_quota: 45,
    priority: 'high',
    is_enabled: true
  },
  {
    profile_name: '法国医疗设备整机厂',
    target_industries: ['medical_device'],
    target_regions: ['western_europe'],
    target_countries: ['FR'],
    company_types: ['oem', 'odm'],
    company_size: '201-500',
    product_lines: ['pcb_connector', 'ffc_fpc'],
    application_scenarios: ['medical_imaging'],
    required_signals: ['具备医疗器械认证信息', '官网展示整机产品而非代理产品'],
    exclude_signals: ['仅销售耗材', '医院或诊所终端'],
    target_roles: ['rd_engineer', 'cto'],
    daily_quota: 30,
    priority: 'medium',
    is_enabled: true
  },
  {
    profile_name: '印度 PCB 与 PCBA 加工厂',
    target_industries: ['pcb_pcba'],
    target_regions: ['south_asia'],
    target_countries: ['IN'],
    company_types: ['ems', 'odm'],
    company_size: '51-200',
    product_lines: ['pin_header', 'pcb_connector'],
    application_scenarios: ['industrial_cabinet', 'led_lighting'],
    required_signals: ['官网展示 SMT 或 PCBA 产能', '有 RFQ / 询价入口'],
    exclude_signals: ['纯贸易无工厂', '网站长期未更新'],
    target_roles: ['purchasing_manager', 'supply_chain_manager'],
    daily_quota: 80,
    priority: 'medium',
    is_enabled: true
  },
  {
    profile_name: '美国工业自动化系统集成商',
    target_industries: ['industrial_automation'],
    target_regions: ['north_america'],
    target_countries: ['US', 'CA'],
    company_types: ['system_integrator'],
    company_size: '11-50',
    product_lines: ['terminal_connector', 'wire_harness'],
    application_scenarios: ['industrial_cabinet'],
    required_signals: ['官网有自动化集成案例'],
    exclude_signals: ['只做软件不涉及硬件'],
    target_roles: ['purchasing_engineer'],
    daily_quota: 40,
    priority: 'medium',
    is_enabled: false
  },
  {
    profile_name: '土耳其安防监控设备厂',
    target_industries: ['security_surveillance'],
    target_regions: ['middle_east'],
    target_countries: ['TR', 'AE'],
    company_types: ['oem', 'brand'],
    company_size: '51-200',
    product_lines: ['waterproof_connector', 'ffc_fpc'],
    application_scenarios: ['security_camera'],
    required_signals: ['自有摄像机或 NVR 产品线'],
    exclude_signals: ['仅安装施工服务商'],
    target_roles: ['purchasing_manager'],
    daily_quota: 35,
    priority: 'low',
    is_enabled: true
  },
  {
    profile_name: '越南消费电子代工厂',
    target_industries: ['consumer_electronics'],
    target_regions: ['southeast_asia'],
    target_countries: ['VN', 'TH'],
    company_types: ['ems'],
    company_size: '501-1000',
    product_lines: ['ffc_fpc', 'pin_header'],
    application_scenarios: ['smart_home'],
    required_signals: ['官网英文站可访问', '展示代工客户或产能规模'],
    exclude_signals: ['仅本地零售'],
    target_roles: ['supply_chain_manager', 'purchasing_engineer'],
    daily_quota: 50,
    priority: 'low',
    is_enabled: false
  },
  {
    profile_name: '波兰储能系统集成商',
    target_industries: ['energy_storage'],
    target_regions: ['central_eastern_europe'],
    target_countries: ['PL', 'DE'],
    company_types: ['system_integrator', 'oem'],
    company_size: '11-50',
    product_lines: ['power_connector'],
    application_scenarios: ['energy_storage_system'],
    required_signals: ['官网展示储能柜或 BESS 方案'],
    exclude_signals: ['光伏安装工程公司'],
    target_roles: ['rd_engineer', 'general_manager'],
    daily_quota: 25,
    priority: 'medium',
    is_enabled: true
  }
]

/** 由种子扩展出 24 条，便于验证分页 */
function buildDataset(): CustomerProfile[] {
  const rows: CustomerProfile[] = []
  seeds.forEach((seed, index) => {
    rows.push({
      id: `PRF-${String(index + 1).padStart(4, '0')}`,
      target_industries: [],
      target_regions: [],
      target_countries: [],
      company_types: [],
      company_size: 'any',
      product_lines: [],
      application_scenarios: [],
      required_signals: [],
      exclude_signals: [],
      target_roles: [],
      daily_quota: 30,
      priority: 'medium',
      is_enabled: true,
      created_at: isoAt(((index * 2) % 20) + 1, 9),
      updated_at: isoAt(((index * 3) % 22) + 1, 14),
      ...seed
    } as CustomerProfile)
  })

  // 扩展批次：复用种子结构，改名与配额，模拟真实环境中的多画像并存
  const suffixes = ['二期', '补充批次', '高配额版', 'A 类客户', '试运行']
  suffixes.forEach((suffix, round) => {
    seeds.slice(0, 4).forEach((seed, index) => {
      const base = rows[index]
      rows.push({
        ...base,
        id: `PRF-${String(rows.length + 1).padStart(4, '0')}`,
        profile_name: `${seed.profile_name} · ${suffix}`,
        daily_quota: Math.max(10, base.daily_quota - round * 5),
        priority: round % 2 === 0 ? 'medium' : 'low',
        is_enabled: (round + index) % 3 !== 0,
        created_at: isoAt(((round + index) % 20) + 1, 10),
        updated_at: isoAt(((round * 2 + index) % 22) + 1, 16)
      })
    })
  })

  return rows
}

/** 内存数据集：模拟数据库，写操作会真实改变后续查询结果 */
const dataset: CustomerProfile[] = buildDataset()

function nextId(): string {
  return `PRF-${String(dataset.length + 1).padStart(4, '0')}`
}

function now(): string {
  const date = new Date()
  const pad = (value: number): string => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

/**
 * 同步查询画像的展示信息（名称 + 启用状态）
 *
 * 供搜索策略以 profile_id 做 JOIN 使用，模拟真实环境的关联查询：
 * 画像改名后，搜索策略列表自动展示最新名称，无需同步冗余字段。
 */
export function getProfileMetaMock(
  id: string
): { profile_name: string; profile_enabled: boolean } | undefined {
  const target = dataset.find((item) => item.id === id)
  if (!target) return undefined
  return { profile_name: target.profile_name, profile_enabled: target.is_enabled }
}

/** 列表：服务端筛选 + 分页语义 */
export function listProfilesMock(query: ProfileQuery): Promise<PageResult<CustomerProfile>> {
  const keyword = query.profile_name?.trim().toLowerCase()

  const filtered = dataset.filter((item) => {
    if (keyword && !item.profile_name.toLowerCase().includes(keyword)) return false
    if (query.target_industry && !item.target_industries.includes(query.target_industry)) {
      return false
    }
    if (query.target_country && !item.target_countries.includes(query.target_country)) {
      return false
    }
    if (typeof query.is_enabled === 'boolean' && item.is_enabled !== query.is_enabled) {
      return false
    }
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
export function getProfileMock(id: string): Promise<CustomerProfile> {
  const target = dataset.find((item) => item.id === id)
  if (!target) return Promise.reject(new Error('画像不存在'))
  return delay({ ...target })
}

/** 新建 */
export function createProfileMock(payload: ProfilePayload): Promise<CustomerProfile> {
  const created: CustomerProfile = {
    ...payload,
    id: nextId(),
    created_at: now(),
    updated_at: now()
  }
  dataset.unshift(created)
  return delay({ ...created })
}

/** 编辑 */
export function updateProfileMock(id: string, payload: ProfilePayload): Promise<CustomerProfile> {
  const index = dataset.findIndex((item) => item.id === id)
  if (index < 0) return Promise.reject(new Error('画像不存在'))
  dataset[index] = { ...dataset[index], ...payload, updated_at: now() }
  return delay({ ...dataset[index] })
}

/** 启用 / 暂停 */
export function updateProfileStatusMock(
  id: string,
  payload: ProfileStatusPayload
): Promise<CustomerProfile> {
  const index = dataset.findIndex((item) => item.id === id)
  if (index < 0) return Promise.reject(new Error('画像不存在'))
  dataset[index] = { ...dataset[index], is_enabled: payload.is_enabled, updated_at: now() }
  return delay({ ...dataset[index] })
}
