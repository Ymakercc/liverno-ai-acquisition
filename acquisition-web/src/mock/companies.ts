/**
 * 候选企业 Mock 服务
 * CLAUDE.md 8.3：Mock 统一放 src/mock，禁止写在 Vue 页面中。
 *
 * 数据模型要点：
 *   enterprises  —— 全局唯一企业实体，同一家企业只有一条
 *   sources      —— 发现来源记录，一条企业可对应多条（不同任务 / 渠道 / Query）
 * 两者通过 enterprise_id 关联，模拟后端 Enterprise + EnterpriseDiscoverySource 的关系。
 */
import { getTaskMetaMock } from './acquisitionTasks'
import type { PageResult } from '@/types/common'
import { getProfileMetaMock } from './profiles'
import type {
  CompanyGrade,
  CompanyQuery,
  CompanyStats,
  DiscoverySummary,
  Enterprise,
  EnterpriseDiscoverySource,
  EnterpriseProfileAnalysis
} from '@/types/company'

const LATENCY = 300
/** 重新分析的模拟耗时 */
const ANALYZE_MIN = 800
const ANALYZE_MAX = 1500

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

function randomAnalyzeDelay(): number {
  return ANALYZE_MIN + Math.floor(Math.random() * (ANALYZE_MAX - ANALYZE_MIN))
}

/* -------------------------------------------------------------------------- */
/* 演示数据                                                                     */
/* -------------------------------------------------------------------------- */

/** 单条画像维度分析的种子声明 */
interface AnalysisSeed {
  /** 该判断所基于的客户画像 */
  profile_id: string
  status: 'pending' | 'analyzed' | 'failed'
  is_relevant?: boolean
  grade?: CompanyGrade
  reason?: string
  failure_reason?: string
}

interface Seed {
  company_name: string
  domain: string
  country: string
  industry: string
  company_type?: string
  /** 发现来源：[任务 id, 渠道, Query] */
  sources: Array<[string, string, string]>
  /** 同一企业可对不同画像有不同判断 */
  analyses: AnalysisSeed[]
  day: number
}

const seeds: Seed[] = [
  {
    company_name: 'Rittal GmbH & Co. KG',
    domain: 'rittal.com',
    country: 'DE',
    industry: 'industrial_automation',
    company_type: 'oem',
    // 同一家企业被 3 个任务、2 个渠道分别发现 —— 全局仍只有一条企业记录
    sources: [
      ['TSK-0001', 'google', '"industrial automation" manufacturer Germany'],
      ['TSK-0001', 'company_site', 'site:.de Automatisierungstechnik terminal block connector'],
      ['TSK-0011', 'google', '"industrial automation" manufacturer Germany'],
      ['TSK-0005', 'google', '"control cabinet" connector manufacturer Germany']
    ],
    analyses: [
      {
        profile_id: 'PRF-0001',
        status: 'analyzed',
        is_relevant: true,
        grade: 'A',
        reason: '官网明确展示控制柜与配电柜整机产品线，含独立的供应商合作页面；产品详情页多次出现 terminal block / connector 关键词，与画像「德国工业控制柜连接器采购商」高度吻合。企业规模与目标区间一致。'
      },
      {
        // 同一家企业，换一个画像判断结果相反 —— 相关性只在画像语境下成立
        profile_id: 'PRF-0009',
        status: 'analyzed',
        is_relevant: true,
        grade: 'B',
        reason: '对「德国工业控制柜连接器采购商 · 二期」画像同样命中，但该画像更强调中小规模厂商，Rittal 体量偏大、采购流程长，降为 B 类。'
      },
      {
        profile_id: 'PRF-0004',
        status: 'analyzed',
        is_relevant: false,
        reason: '对画像「印度 PCB 与 PCBA 加工厂」不相关：该企业不在目标国家范围内，且不属于 PCBA 代工类型。'
      }
    ],
    day: 22
  },
  {
    company_name: 'Phoenix Contact Deutschland GmbH',
    domain: 'phoenixcontact.com',
    country: 'DE',
    industry: 'connector_harness',
    company_type: 'oem',
    sources: [
      ['TSK-0001', 'google', '"terminal block connector" supplier Germany'],
      ['TSK-0011', 'b2b', 'kompass terminal block connector supplier']
    ],
    analyses: [
      {
        profile_id: 'PRF-0001',
        status: 'analyzed',
        is_relevant: true,
        grade: 'A',
        reason: '连接器与工业自动化元件制造商，自有产线与品牌；官网有明确的采购与供应商入口。属于目标行业核心厂商。'
      }
    ],
    day: 22
  },
  {
    company_name: 'Eldon Holding AB (Germany)',
    domain: 'eldon.com',
    country: 'DE',
    industry: 'industrial_automation',
    company_type: 'oem',
    sources: [['TSK-0001', 'company_site', 'site:.de Automatisierungstechnik terminal block connector']],
    analyses: [
      {
        profile_id: 'PRF-0001',
        status: 'analyzed',
        is_relevant: true,
        grade: 'B',
        reason: '控制柜与机柜制造商，产品线匹配；但官网未展示明确的连接器采购需求，需进一步确认采购规模。'
      }
    ],
    day: 22
  },
  {
    company_name: 'Elektro-Handel Müller GmbH',
    domain: 'elektro-mueller.de',
    country: 'DE',
    industry: 'industrial_automation',
    company_type: 'distributor',
    sources: [['TSK-0001', 'google', '"industrial automation" manufacturer Germany']],
    analyses: [
      {
        profile_id: 'PRF-0001',
        status: 'analyzed',
        is_relevant: false,
        reason: '本地电气产品零售商，无自有制造或系统集成业务，命中画像的排除条件「纯电商零售网站」。不进入待开发客户池。'
      }
    ],
    day: 22
  },
  {
    company_name: 'Alfen N.V.',
    domain: 'alfen.com',
    country: 'NL',
    industry: 'energy_storage',
    company_type: 'oem',
    sources: [
      ['TSK-0002', 'google', '"energy storage" manufacturer Italy'],
      ['TSK-0001', 'b2b', 'europages industrial automation manufacturer Germany']
    ],
    analyses: [
      {
        profile_id: 'PRF-0002',
        status: 'analyzed',
        is_relevant: true,
        grade: 'A',
        reason: '充电桩与储能系统整机厂，近一年有新品发布与展会信息；产品需要电源连接器与防水连接器，与匹配产品线一致。'
      },
      {
        // 被德国工业控制柜任务也发现了，但该画像下尚未分析
        profile_id: 'PRF-0001',
        status: 'pending'
      }
    ],
    day: 21
  },
  {
    company_name: 'Scame Parre S.p.A.',
    domain: 'scame.com',
    country: 'IT',
    industry: 'connector_harness',
    company_type: 'oem',
    sources: [['TSK-0002', 'company_site', 'site:.it automazione industriale power connector']],
    analyses: [
      {
        profile_id: 'PRF-0002',
        status: 'analyzed',
        is_relevant: true,
        grade: 'B',
        reason: '意大利工业连接器与配电产品制造商，产品线与画像部分重叠；但自身即为连接器厂商，采购意愿需人工确认。'
      }
    ],
    day: 21
  },
  {
    company_name: 'EV Charge Service Italia S.r.l.',
    domain: 'evchargeservice.it',
    country: 'IT',
    industry: 'energy_storage',
    company_type: 'end_user',
    sources: [['TSK-0002', 'google', 'automazione industriale produttore']],
    analyses: [
      {
        profile_id: 'PRF-0002',
        status: 'analyzed',
        is_relevant: false,
        reason: '仅提供充电桩运营与安装服务，不生产硬件，命中排除条件「仅做充电运营服务、不生产硬件」。'
      }
    ],
    day: 21
  },
  {
    company_name: 'Siemens Healthineers AG',
    domain: 'siemens-healthineers.com',
    country: 'DE',
    industry: 'medical_device',
    company_type: 'oem',
    sources: [
      ['TSK-0007', 'google', '"medical imaging equipment" manufacturer France'],
      ['TSK-0001', 'google', '"industrial automation" manufacturer Germany']
    ],
    analyses: [
      {
        profile_id: 'PRF-0003',
        status: 'analyzed',
        is_relevant: true,
        grade: 'B',
        reason: '医疗影像设备整机厂，具备医疗器械认证信息；PCB 连接器与 FFC/FPC 有明确使用场景。但采购决策链长、门槛高，优先级中等。'
      },
      {
        profile_id: 'PRF-0001',
        status: 'analyzed',
        is_relevant: false,
        reason: '对画像「德国工业控制柜连接器采购商」不相关：主营医疗影像设备，不涉及工业控制柜与配电柜产品线。'
      }
    ],
    day: 18
  },
  {
    company_name: 'Thales SA - Medical Division',
    domain: 'thalesgroup.com',
    country: 'FR',
    industry: 'medical_device',
    company_type: 'oem',
    sources: [['TSK-0007', 'google', '"medical imaging equipment" manufacturer France']],
    analyses: [
      {
        profile_id: 'PRF-0003',
        status: 'pending'
      }
    ],
    day: 18
  },
  {
    company_name: 'Bharat Circuits Pvt. Ltd.',
    domain: 'bharatcircuits.in',
    country: 'IN',
    industry: 'pcb_pcba',
    company_type: 'ems',
    sources: [
      ['TSK-0003', 'tradeindia', 'tradeindia PCB assembly manufacturer'],
      ['TSK-0017', 'google', '"PCB assembly" supplier India']
    ],
    analyses: [
      {
        profile_id: 'PRF-0004',
        status: 'analyzed',
        is_relevant: true,
        grade: 'A',
        reason: '官网展示 SMT 产线与 PCBA 产能，设有 RFQ 询价入口；排针排母与 PCB 连接器为其常规采购件，匹配度高。'
      }
    ],
    day: 23
  },
  {
    company_name: 'Shree Electronics Trading Co.',
    domain: 'shree-electronics-trading.in',
    country: 'IN',
    industry: 'pcb_pcba',
    company_type: 'trading',
    sources: [['TSK-0003', 'tradeindia', 'tradeindia pin header buyer']],
    analyses: [
      {
        profile_id: 'PRF-0004',
        status: 'analyzed',
        is_relevant: false,
        reason: '纯贸易公司，无自有工厂，命中排除条件「纯贸易无工厂」。'
      }
    ],
    day: 23
  },
  {
    company_name: 'Nova PCB Industries',
    domain: 'novapcb.in',
    country: 'IN',
    industry: 'pcb_pcba',
    company_type: 'odm',
    sources: [['TSK-0003', 'b2b', 'kompass pin header supplier']],
    analyses: [
      {
        profile_id: 'PRF-0004',
        status: 'pending'
      }
    ],
    day: 23
  },
  {
    company_name: 'Rockwell Automation Inc.',
    domain: 'rockwellautomation.com',
    country: 'US',
    industry: 'industrial_automation',
    company_type: 'oem',
    sources: [['TSK-0013', 'google', '"industrial automation" manufacturer United States']],
    analyses: [
      {
        profile_id: 'PRF-0014',
        status: 'analyzed',
        is_relevant: true,
        grade: 'A',
        reason: '工业自动化头部厂商，控制柜与伺服驱动产品线齐全，端子连接器与线束组件为持续采购件。'
      }
    ],
    day: 13
  },
  {
    company_name: 'Midwest Control Systems LLC',
    domain: 'midwestcontrols.com',
    country: 'US',
    industry: 'industrial_automation',
    company_type: 'system_integrator',
    sources: [
      ['TSK-0013', 'company_site', 'site:.com control cabinet manufacturer'],
      ['TSK-0006', 'google', '"system integrator" industrial automation United States']
    ],
    analyses: [
      {
        profile_id: 'PRF-0014',
        status: 'analyzed',
        is_relevant: true,
        grade: 'B',
        reason: '系统集成商，官网有自动化集成案例；采购量中等，作为 B 类跟进。'
      }
    ],
    day: 13
  },
  {
    company_name: 'AutomationSoft Solutions',
    domain: 'automationsoft.us',
    country: 'US',
    industry: 'industrial_automation',
    company_type: 'system_integrator',
    sources: [['TSK-0006', 'google', '"system integrator" industrial automation United States']],
    analyses: [
      {
        profile_id: 'PRF-0005',
        status: 'analyzed',
        is_relevant: false,
        reason: '仅提供自动化软件与 SCADA 系统，不涉及硬件，命中排除条件「只做软件不涉及硬件」。'
      }
    ],
    day: 19
  },
  {
    company_name: 'Vestel Savunma ve Güvenlik',
    domain: 'vestelsavunma.com',
    country: 'TR',
    industry: 'security_surveillance',
    company_type: 'oem',
    sources: [['TSK-0015', 'google', '"security camera" manufacturer Turkey']],
    analyses: [
      {
        profile_id: 'PRF-0006',
        status: 'analyzed',
        is_relevant: true,
        grade: 'B',
        reason: '自有摄像机与安防设备产品线，防水连接器与 FFC/FPC 有直接应用场景。'
      }
    ],
    day: 11
  },
  {
    company_name: 'Anadolu Güvenlik Kurulum',
    domain: 'anadolu-guvenlik.com.tr',
    country: 'TR',
    industry: 'security_surveillance',
    company_type: 'end_user',
    sources: [['TSK-0015', 'google', '"security camera" manufacturer Turkey']],
    analyses: [
      {
        profile_id: 'PRF-0006',
        status: 'failed',
        failure_reason: 'AI 分析超时：企业官网多次请求返回 403，未能获取足够内容用于判断'
      }
    ],
    day: 11
  },
  {
    company_name: 'VinFast Electronics JSC',
    domain: 'vinfast-electronics.vn',
    country: 'VN',
    industry: 'consumer_electronics',
    company_type: 'ems',
    sources: [
      ['TSK-0009', 'google', '"consumer electronics" EMS Vietnam'],
      ['TSK-0009', 'b2b', 'europages EMS provider Vietnam']
    ],
    analyses: [
      {
        profile_id: 'PRF-0007',
        status: 'analyzed',
        is_relevant: true,
        grade: 'B',
        reason: '代工厂，官网英文站可访问并展示产能规模；FFC/FPC 与排针排母为常规用料。'
      }
    ],
    day: 17
  },
  {
    company_name: 'Saigon Retail Electronics',
    domain: 'saigon-retail.vn',
    country: 'VN',
    industry: 'consumer_electronics',
    company_type: 'distributor',
    sources: [['TSK-0009', 'google', 'tự động hóa công nghiệp nhà sản xuất']],
    analyses: [
      {
        profile_id: 'PRF-0007',
        status: 'analyzed',
        is_relevant: false,
        reason: '本地零售商，命中排除条件「仅本地零售」。'
      }
    ],
    day: 17
  },
  {
    company_name: 'Energa Magazyny Energii Sp. z o.o.',
    domain: 'energa-storage.pl',
    country: 'PL',
    industry: 'energy_storage',
    company_type: 'system_integrator',
    sources: [['TSK-0005', 'google', 'Schaltschrank Hersteller Deutschland']],
    analyses: [
      {
        profile_id: 'PRF-0009',
        status: 'pending'
      }
    ],
    day: 23
  },
  {
    company_name: 'Lumina LED Sistemleri',
    domain: 'luminaled.com.tr',
    country: 'TR',
    industry: 'consumer_electronics',
    company_type: 'oem',
    sources: [['TSK-0004', 'google', '"security surveillance" manufacturer Turkey']],
    analyses: [
      {
        profile_id: 'PRF-0006',
        status: 'analyzed',
        is_relevant: true,
        grade: 'C',
        reason: 'LED 照明产品制造商，可能使用防水连接器，但与主力产品线相关度较低，作为 C 类低优先级保留。'
      }
    ],
    day: 20
  },
  {
    company_name: 'Medtech Imaging France SAS',
    domain: 'medtech-imaging.fr',
    country: 'FR',
    industry: 'medical_device',
    company_type: 'odm',
    sources: [['TSK-0014', 'google', '"medical device" manufacturer France Spain']],
    analyses: [
      {
        profile_id: 'PRF-0011',
        status: 'failed',
        failure_reason: 'AI 分析失败：模型返回内容无法解析为结构化判断结果'
      }
    ],
    day: 12
  }
]

/* -------------------------------------------------------------------------- */
/* 建模：企业实体 / 发现来源 / 画像维度分析 三张表分开存储                        */
/* -------------------------------------------------------------------------- */

let sourceSeed = 0
let analysisSeed = 0

/** 发现来源表：一条企业可对应多条来源 */
const sources: EnterpriseDiscoverySource[] = []

/**
 * 画像维度分析表
 * 一条企业 × 一个画像可以有多条记录（历史），最新一条为当前结论。
 */
const analyses: EnterpriseProfileAnalysis[] = []

function makeAnalysis(
  enterpriseId: string,
  seed: AnalysisSeed,
  analyzedAt: string
): EnterpriseProfileAnalysis {
  analysisSeed += 1
  const base = {
    id: `EPA-${String(analysisSeed).padStart(5, '0')}`,
    enterprise_id: enterpriseId,
    profile_id: seed.profile_id
  }

  if (seed.status === 'analyzed') {
    return {
      ...base,
      status: 'analyzed',
      is_relevant: seed.is_relevant ?? false,
      // grade 仅在 is_relevant = true 时有意义
      grade: seed.is_relevant ? (seed.grade ?? 'C') : null,
      reason: seed.reason ?? '',
      analyzed_at: analyzedAt
    }
  }
  if (seed.status === 'failed') {
    return {
      ...base,
      status: 'failed',
      is_relevant: null,
      grade: null,
      reason: '',
      failure_reason: seed.failure_reason
    }
  }
  return { ...base, status: 'pending', is_relevant: null, grade: null, reason: '' }
}

/** 企业实体表：全局唯一，只保存企业自身事实，不含任何相关性判断 */
const enterprises: Enterprise[] = seeds.map((seed, index) => {
  const id = `ENT-${String(index + 1).padStart(5, '0')}`

  seed.sources.forEach(([taskId, channel, query], sourceIndex) => {
    const meta = getTaskMetaMock(taskId)
    sourceSeed += 1
    sources.push({
      id: `EDS-${String(sourceSeed).padStart(5, '0')}`,
      enterprise_id: id,
      task_id: taskId,
      task_name: meta?.task_name ?? taskId,
      strategy_id: meta?.strategy_id ?? '-',
      strategy_code: meta?.strategy_id ?? '-',
      strategy_version: meta?.strategy_version ?? 1,
      channel,
      query,
      provider: 'mock',
      result_url: `https://www.${seed.domain}`,
      discovered_at: `2026-09-${String(seed.day).padStart(2, '0')} 0${8 + (sourceIndex % 2)}:4${sourceIndex}:00`
    })
  })

  seed.analyses.forEach((item) => {
    analyses.push(makeAnalysis(id, item, `2026-09-${String(seed.day).padStart(2, '0')} 10:20:00`))
  })

  return {
    id,
    company_name: seed.company_name,
    // 标准化：去掉常见公司后缀与标点，用于「名称归一 + 国家」这一去重键
    normalized_name: seed.company_name
      .replace(/\b(GmbH|Co\.|KG|AG|S\.p\.A\.|SAS|Inc\.|LLC|Ltd\.|Pvt\.|N\.V\.|AB|JSC|S\.r\.l\.|Sp\. z o\.o\.)\b/g, '')
      .replace(/[.,&]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase(),
    domain: seed.domain,
    website: `https://www.${seed.domain}`,
    country: seed.country,
    industry: seed.industry,
    company_type: seed.company_type,
    email_domain: seed.domain,
    discovery_summary: {
      strategy_count: 0,
      channels: [],
      latest_strategy_id: '',
      latest_strategy_code: '',
      latest_discovered_at: ''
    },
    first_discovered_at: `2026-09-${String(seed.day).padStart(2, '0')} 08:40:00`,
    created_at: `2026-09-${String(seed.day).padStart(2, '0')} 08:40:00`,
    updated_at: `2026-09-${String(seed.day).padStart(2, '0')} 10:25:00`
  }
})

/** 取某企业的全部发现来源 */
function sourcesOf(enterpriseId: string): EnterpriseDiscoverySource[] {
  return sources.filter((item) => item.enterprise_id === enterpriseId)
}

/**
 * 取某企业在某画像下的【最新一次】分析
 * 历史记录全部保留，这里只挑最后写入的一条作为当前结论。
 */
function latestAnalysis(
  enterpriseId: string,
  profileId: string | undefined
): EnterpriseProfileAnalysis | undefined {
  if (!profileId) return undefined
  const list = analyses.filter(
    (item) => item.enterprise_id === enterpriseId && item.profile_id === profileId
  )
  if (!list.length) return undefined
  const latest = list[list.length - 1]
  return {
    ...latest,
    profile_name: getProfileMetaMock(latest.profile_id)?.profile_name
  }
}

/** 该企业已有分析记录的画像清单，供详情页切换查看 */
function analysisProfilesOf(
  enterpriseId: string
): Array<{ profile_id: string; profile_name: string }> {
  const ids = Array.from(
    new Set(analyses.filter((item) => item.enterprise_id === enterpriseId).map((i) => i.profile_id))
  )
  return ids.map((profileId) => ({
    profile_id: profileId,
    profile_name: getProfileMetaMock(profileId)?.profile_name ?? profileId
  }))
}

/** 由来源表聚合出列表摘要 */
function summaryOf(enterpriseId: string): DiscoverySummary {
  const list = sourcesOf(enterpriseId)
  const latest = [...list].sort((a, b) => b.discovered_at.localeCompare(a.discovered_at))[0]
  return {
    strategy_count: new Set(list.map((item) => item.strategy_id)).size,
    channels: Array.from(new Set(list.map((item) => item.channel))),
    latest_strategy_id: latest?.strategy_id ?? '',
    latest_strategy_code: latest?.strategy_code ?? '',
    latest_discovered_at: latest?.discovered_at ?? ''
  }
}

/** 组装列表 / 详情返回：附加来源摘要与「当前画像语境下」的分析 */
function withContext(enterprise: Enterprise, profileId: string | undefined): Enterprise {
  return {
    ...enterprise,
    discovery_summary: summaryOf(enterprise.id),
    analysis: latestAnalysis(enterprise.id, profileId)
  }
}

/**
 * 解析画像语境
 * 传了 task_id 以任务的 profile_id 为准，否则用显式 profile_id。
 */
function resolveProfileId(query: { task_id?: string; profile_id?: string }): string | undefined {
  if (query.task_id) return getTaskMetaMock(query.task_id)?.profile_id
  return query.profile_id
}

/**
 * 同步查询企业元信息
 * 供联系人模块 JOIN Enterprise 使用，真实环境由后端 join 返回。
 */
export function getEnterpriseMetaMock(
  id: string
): { company_name: string; domain: string } | undefined {
  const target = enterprises.find((item) => item.id === id)
  if (!target) return undefined
  return { company_name: target.company_name, domain: target.domain }
}

/**
 * 企业在任一画像下是否存在 relevant 的最新分析
 * 这是「具备进入后续开发链路资格」的判断依据（CLAUDE.md 9.3.1）。
 */
export function hasRelevantAnalysisMock(enterpriseId: string): boolean {
  const profileIds = Array.from(
    new Set(
      analyses.filter((item) => item.enterprise_id === enterpriseId).map((item) => item.profile_id)
    )
  )
  return profileIds.some((profileId) => latestAnalysis(enterpriseId, profileId)?.is_relevant === true)
}

/* -------------------------------------------------------------------------- */
/* 服务方法                                                                     */
/* -------------------------------------------------------------------------- */

function matchRelevance(
  analysis: EnterpriseProfileAnalysis | undefined,
  relevance: string
): boolean {
  // 该画像下尚无分析记录，等同于「待分析」
  if (!analysis) return relevance === 'pending'
  if (relevance === 'relevant') return analysis.status === 'analyzed' && analysis.is_relevant === true
  if (relevance === 'not_relevant') {
    return analysis.status === 'analyzed' && analysis.is_relevant === false
  }
  if (relevance === 'pending') return analysis.status === 'pending'
  if (relevance === 'failed') return analysis.status === 'failed'
  return true
}

/** 列表：服务端筛选 + 分页语义；relevance / grade 在画像语境下生效 */
export function listCompaniesMock(query: CompanyQuery): Promise<PageResult<Enterprise>> {
  const keyword = query.company_name?.trim().toLowerCase()
  const profileId = resolveProfileId(query)

  const filtered = enterprises.filter((item) => {
    if (keyword) {
      const hit =
        item.company_name.toLowerCase().includes(keyword) ||
        item.normalized_name.includes(keyword) ||
        item.domain.toLowerCase().includes(keyword)
      if (!hit) return false
    }
    if (query.country && item.country !== query.country) return false
    if (query.industry && item.industry !== query.industry) return false

    const list = sourcesOf(item.id)
    if (query.channel && !list.some((source) => source.channel === query.channel)) return false
    if (query.task_id && !list.some((source) => source.task_id === query.task_id)) return false

    const analysis = latestAnalysis(item.id, profileId)
    if (query.relevance && !matchRelevance(analysis, query.relevance)) return false
    if (query.grade && analysis?.grade !== query.grade) return false
    return true
  })

  const start = (query.page - 1) * query.page_size
  return delay({
    list: filtered.slice(start, start + query.page_size).map((item) => withContext(item, profileId)),
    total: filtered.length,
    page: query.page,
    page_size: query.page_size
  })
}

/** 详情：发现来源与分析结果随详情一起返回，不单独拆接口 */
export function getCompanyMock(id: string, profileId?: string): Promise<Enterprise> {
  const target = enterprises.find((item) => item.id === id)
  if (!target) return Promise.reject(new Error('企业不存在'))

  const profiles = analysisProfilesOf(id)
  // 未指定画像时，默认取该企业已有分析记录中的第一个画像，避免语境不明
  const contextProfile = profileId ?? profiles[0]?.profile_id

  return delay({
    ...withContext(structuredClone(target), contextProfile),
    discovery_sources: structuredClone(sourcesOf(id)),
    analysis_profiles: profiles
  })
}

/**
 * 重新分析（模拟 AI）
 *
 * 关键语义：**追加一条新的分析记录，不覆盖历史**。
 * 接口返回该 enterprise + profile 下的最新一条。
 */
export function reanalyzeCompanyMock(id: string, profileId: string): Promise<Enterprise> {
  const target = enterprises.find((item) => item.id === id)
  if (!target) return Promise.reject(new Error('企业不存在'))
  if (!profileId) return Promise.reject(new Error('缺少画像语境，无法进行相关性分析'))

  const profileName = getProfileMetaMock(profileId)?.profile_name ?? profileId
  // 用企业 id + 画像 id 做确定性判定，保证同一组合结果稳定
  const seedNumber = Number(`${id}${profileId}`.replace(/\D/g, '').slice(-4))
  const relevant = seedNumber % 4 !== 0
  const grade: CompanyGrade = (['A', 'B', 'C'][seedNumber % 3] as CompanyGrade) ?? 'C'

  analysisSeed += 1
  analyses.push({
    id: `EPA-${String(analysisSeed).padStart(5, '0')}`,
    enterprise_id: id,
    profile_id: profileId,
    status: 'analyzed',
    is_relevant: relevant,
    grade: relevant ? grade : null,
    reason: relevant
      ? `重新分析：官网内容与画像「${profileName}」的目标行业、产品线与应用场景匹配，未命中排除条件，判定为有效目标企业（${grade} 类）。`
      : `重新分析：官网主营业务与画像「${profileName}」偏离，或命中其排除条件，判定为不相关。历史分析记录保留，画像调整后可再次分析。`,
    analyzed_at: now()
  })

  target.updated_at = now()

  return delay(
    {
      ...withContext(structuredClone(target), profileId),
      discovery_sources: structuredClone(sourcesOf(id)),
      analysis_profiles: analysisProfilesOf(id)
    },
    randomAnalyzeDelay()
  )
}

/** 顶部统计：同样是画像语境下的统计 */
export function getCompanyStatsMock(params: {
  task_id?: string
  profile_id?: string
}): Promise<CompanyStats> {
  const profileId = resolveProfileId(params)
  const scoped = params.task_id
    ? enterprises.filter((item) =>
        sourcesOf(item.id).some((source) => source.task_id === params.task_id)
      )
    : enterprises

  const analysisList = scoped.map((item) => latestAnalysis(item.id, profileId))
  return delay({
    total: scoped.length,
    relevant: analysisList.filter((item) => matchRelevance(item, 'relevant')).length,
    not_relevant: analysisList.filter((item) => matchRelevance(item, 'not_relevant')).length,
    pending: analysisList.filter(
      (item) => matchRelevance(item, 'pending') || matchRelevance(item, 'failed')
    ).length
  })
}
