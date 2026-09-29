/**
 * 搜索策略 Mock 服务
 * CLAUDE.md 8.3：Mock 统一放 src/mock，禁止写在 Vue 页面中。
 *
 * 该 Mock 完整模拟服务端语义：筛选、分页、AI 生成、保存、编辑、启用、暂停、重新生成。
 * AI 生成部分按画像字段推导 Query，模拟真实 LLM 输出结构；
 * 后端就绪后只需切换 src/api/strategy.ts 的开关，页面与类型均不改动。
 */
import { getProfileMock, getProfileMetaMock } from './profiles'
import { CHANNEL_OPTIONS } from './dict'
import type { PageResult } from '@/types/common'
import type { CustomerProfile } from '@/types/profile'
import { ApiError } from '@/api/request'
import {
  ACTIVATE_HINT,
  STRATEGY_VERSION_CONFLICT,
  VERSION_CONFLICT_HINT,
  canActivate
} from '@/types/strategy'
import type {
  ChannelSearchStrategy,
  SearchQuery,
  SearchStrategy,
  StrategyQuery,
  StrategyStats,
  StrategyStatus,
  StrategyStatusPayload,
  StrategyUpdatePayload
} from '@/types/strategy'

const LATENCY = 300
/** AI 生成模拟耗时区间 */
const GENERATE_MIN = 800
const GENERATE_MAX = 1500

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

/* -------------------------------------------------------------------------- */
/* AI 生成用的英文词表：真实检索面向海外，Query 使用英文更接近实际投放           */
/* 仅 Mock 内部使用，后端接入真实 LLM 后整体由后端产出                          */
/* -------------------------------------------------------------------------- */

const EN_INDUSTRY: Record<string, string> = {
  connector_harness: 'connector and wire harness',
  pcb_pcba: 'PCB assembly',
  power_module: 'power module',
  industrial_automation: 'industrial automation',
  automotive_electronics: 'automotive electronics',
  medical_device: 'medical device',
  energy_storage: 'energy storage',
  consumer_electronics: 'consumer electronics',
  security_surveillance: 'security surveillance',
  telecom_equipment: 'telecom equipment'
}

const EN_PRODUCT: Record<string, string> = {
  terminal_connector: 'terminal block connector',
  wire_harness: 'wire harness assembly',
  pcb_connector: 'PCB connector',
  power_connector: 'power connector',
  waterproof_connector: 'waterproof connector',
  rf_connector: 'RF connector',
  pin_header: 'pin header',
  ffc_fpc: 'FFC FPC connector'
}

const EN_SCENARIO: Record<string, string> = {
  industrial_cabinet: 'control cabinet',
  ev_charger: 'EV charging station',
  energy_storage_system: 'battery energy storage system',
  servo_drive: 'servo drive',
  medical_imaging: 'medical imaging equipment',
  in_vehicle: 'in-vehicle electronics',
  smart_home: 'smart home device',
  led_lighting: 'LED lighting',
  security_camera: 'security camera',
  telecom_base_station: 'telecom base station'
}

const EN_COMPANY_TYPE: Record<string, string> = {
  oem: 'manufacturer',
  odm: 'ODM',
  brand: 'brand owner',
  distributor: 'distributor',
  trading: 'trading company',
  system_integrator: 'system integrator',
  ems: 'EMS provider',
  end_user: 'end user'
}

const COUNTRY_EN: Record<string, string> = {
  DE: 'Germany',
  IT: 'Italy',
  FR: 'France',
  ES: 'Spain',
  NL: 'Netherlands',
  PL: 'Poland',
  GB: 'United Kingdom',
  TR: 'Turkey',
  US: 'United States',
  CA: 'Canada',
  MX: 'Mexico',
  BR: 'Brazil',
  AE: 'United Arab Emirates',
  IN: 'India',
  VN: 'Vietnam',
  TH: 'Thailand',
  MY: 'Malaysia',
  ID: 'Indonesia',
  JP: 'Japan',
  KR: 'South Korea',
  AU: 'Australia'
}

/** 国家顶级域，供企业官网渠道的 site: 限定使用 */
const COUNTRY_TLD: Record<string, string> = {
  DE: '.de',
  IT: '.it',
  FR: '.fr',
  ES: '.es',
  NL: '.nl',
  PL: '.pl',
  GB: '.co.uk',
  TR: '.com.tr',
  US: '.com',
  CA: '.ca',
  MX: '.mx',
  BR: '.com.br',
  AE: '.ae',
  IN: '.in',
  VN: '.vn',
  TH: '.co.th',
  MY: '.com.my',
  ID: '.co.id',
  JP: '.co.jp',
  KR: '.co.kr',
  AU: '.com.au'
}

/**
 * 当地语言的行业词（模拟 AI 的多语言能力）
 * 说明：language 由「AI」在生成每条 Query 时决定，允许同一国家同时产出
 * 英文与当地语言 Query，不存在「国家 → 语言」的固定映射。
 */
const LOCAL_TERMS: Record<string, { lang: string; industry: string; role: string }> = {
  DE: { lang: 'de', industry: 'Automatisierungstechnik', role: 'Hersteller' },
  IT: { lang: 'it', industry: 'automazione industriale', role: 'produttore' },
  FR: { lang: 'fr', industry: 'automatisation industrielle', role: 'fabricant' },
  ES: { lang: 'es', industry: 'automatización industrial', role: 'fabricante' },
  NL: { lang: 'nl', industry: 'industriële automatisering', role: 'fabrikant' },
  PL: { lang: 'pl', industry: 'automatyka przemysłowa', role: 'producent' },
  TR: { lang: 'tr', industry: 'endüstriyel otomasyon', role: 'üretici' },
  BR: { lang: 'pt', industry: 'automação industrial', role: 'fabricante' },
  JP: { lang: 'ja', industry: '産業用オートメーション', role: 'メーカー' },
  KR: { lang: 'ko', industry: '산업 자동화', role: '제조업체' },
  VN: { lang: 'vi', industry: 'tự động hóa công nghiệp', role: 'nhà sản xuất' }
}

function en(map: Record<string, string>, value: string | undefined): string {
  if (!value) return ''
  return map[value] ?? value
}

let querySeed = 0
/** language 由生成方（AI）显式给出，不在此处按国家推导 */
function makeQuery(
  text: string,
  country: string | undefined,
  language: string | undefined = 'en'
): SearchQuery {
  querySeed += 1
  return {
    id: `SQ-${String(querySeed).padStart(5, '0')}`,
    query_text: text,
    country_code: country,
    language,
    enabled: true
  }
}

/* -------------------------------------------------------------------------- */
/* AI 生成：按画像字段推导各渠道 Query                                          */
/* -------------------------------------------------------------------------- */

function buildChannelStrategies(profile: CustomerProfile): ChannelSearchStrategy[] {
  const countries = profile.target_countries.length ? profile.target_countries : ['DE']
  const industries = profile.target_industries.map((item) => en(EN_INDUSTRY, item)).filter(Boolean)
  const products = profile.product_lines.map((item) => en(EN_PRODUCT, item)).filter(Boolean)
  const scenarios = profile.application_scenarios
    .map((item) => en(EN_SCENARIO, item))
    .filter(Boolean)
  const types = profile.company_types.map((item) => en(EN_COMPANY_TYPE, item)).filter(Boolean)

  const mainIndustry = industries[0] ?? 'industrial'
  const mainType = types[0] ?? 'manufacturer'
  const excludeHint = profile.exclude_signals.length ? ' -distributor -marketplace' : ''

  /* Google：行业 / 产品 / 场景 × 国家 组合，附带排除词 */
  const googleQueries: SearchQuery[] = []
  countries.slice(0, 3).forEach((country) => {
    const countryName = en(COUNTRY_EN, country)
    const local = LOCAL_TERMS[country]

    // 英文 Query：覆盖面广，多数 B2B 厂商官网有英文版
    googleQueries.push(
      makeQuery(`"${mainIndustry}" ${mainType} ${countryName}${excludeHint}`, country, 'en')
    )
    if (products[0]) {
      googleQueries.push(makeQuery(`"${products[0]}" supplier ${countryName}`, country, 'en'))
    }
    // 当地语言 Query：命中只做本地站点的中小厂商
    if (local) {
      googleQueries.push(makeQuery(`${local.industry} ${local.role}`, country, local.lang))
    }
    if (scenarios[0]) {
      googleQueries.push(makeQuery(`${scenarios[0]} manufacturer ${countryName}`, country, 'en'))
    }
  })

  /* 企业官网：site: 限定国家顶级域，直接命中厂商官网 */
  const siteQueries: SearchQuery[] = countries.slice(0, 3).map((country) => {
    const local = LOCAL_TERMS[country]
    return makeQuery(
      `site:${COUNTRY_TLD[country] ?? '.com'} ${local ? local.industry : mainIndustry} ${products[0] ?? ''}`.trim(),
      country,
      local ? local.lang : 'en'
    )
  })
  if (profile.required_signals[0]) {
    siteQueries.push(
      makeQuery(
        `"${mainIndustry}" "${products[0] ?? mainIndustry}" contact purchasing`,
        countries[0],
        'en'
      )
    )
  }

  /* TradeIndia：印度 B2B，主要面向采购方与制造商 */
  const tradeIndiaQueries: SearchQuery[] = [
    makeQuery(`tradeindia ${products[0] ?? mainIndustry} buyer`, 'IN', 'en'),
    makeQuery(`tradeindia ${mainIndustry} ${mainType}`, 'IN', 'en')
  ]
  if (products[1]) {
    tradeIndiaQueries.push(makeQuery(`tradeindia ${products[1]} manufacturer`, 'IN', 'en'))
  }

  /* 其他 B2B 平台：欧洲与全球通用目录 */
  const b2bQueries: SearchQuery[] = countries.slice(0, 2).map((country) =>
    makeQuery(`europages ${mainIndustry} ${mainType} ${en(COUNTRY_EN, country)}`, country, 'en')
  )
  b2bQueries.push(makeQuery(`kompass ${products[0] ?? mainIndustry} supplier`, countries[0], 'en'))

  return [
    {
      channel: 'google',
      enabled: true,
      target_countries: countries,
      strategy_summary: `以「${mainIndustry}」为核心词，叠加企业类型与目标国家做组合检索；已按画像排除条件追加否定词，优先命中厂商官网而非目录站。`,
      queries: googleQueries
    },
    {
      channel: 'company_site',
      enabled: true,
      target_countries: countries,
      strategy_summary: '用 site: 限定各目标国家顶级域，直接抓取本土制造商官网，命中率高但数量有限，作为质量兜底渠道。',
      queries: siteQueries
    },
    {
      channel: 'tradeindia',
      enabled: countries.includes('IN'),
      target_countries: ['IN'],
      strategy_summary: '面向印度市场的 B2B 平台，适合批量获取采购方与代工厂；画像未覆盖印度时默认关闭。',
      queries: tradeIndiaQueries
    },
    {
      channel: 'b2b',
      enabled: true,
      target_countries: countries,
      strategy_summary: '欧洲与全球通用 B2B 目录（Europages / Kompass），覆盖面广，需配合 AI 相关性判断过滤目录型公司。',
      queries: b2bQueries
    }
  ]
}

/* -------------------------------------------------------------------------- */
/* 演示数据集                                                                   */
/* -------------------------------------------------------------------------- */

interface Seed {
  profile_id: string
  profile_name: string
  status: StrategyStatus
  version: number
  channels: string[]
  queryCount: number
  countries: string[]
  day: number
}

const seeds: Seed[] = [
  { profile_id: 'PRF-0001', profile_name: '德国工业控制柜连接器采购商', status: 'active', version: 3, channels: ['google', 'company_site', 'b2b'], queryCount: 12, countries: ['DE', 'NL'], day: 22 },
  { profile_id: 'PRF-0002', profile_name: '意大利新能源充电桩制造商', status: 'active', version: 2, channels: ['google', 'company_site', 'b2b'], queryCount: 9, countries: ['IT', 'ES'], day: 21 },
  { profile_id: 'PRF-0003', profile_name: '法国医疗设备整机厂', status: 'draft', version: 1, channels: ['google', 'company_site'], queryCount: 6, countries: ['FR'], day: 20 },
  { profile_id: 'PRF-0004', profile_name: '印度 PCB 与 PCBA 加工厂', status: 'active', version: 4, channels: ['google', 'tradeindia', 'b2b'], queryCount: 14, countries: ['IN'], day: 19 },
  { profile_id: 'PRF-0005', profile_name: '美国工业自动化系统集成商', status: 'paused', version: 2, channels: ['google', 'company_site'], queryCount: 7, countries: ['US', 'CA'], day: 18 },
  { profile_id: 'PRF-0006', profile_name: '土耳其安防监控设备厂', status: 'active', version: 1, channels: ['google', 'b2b'], queryCount: 8, countries: ['TR', 'AE'], day: 17 },
  { profile_id: 'PRF-0007', profile_name: '越南消费电子代工厂', status: 'paused', version: 3, channels: ['google', 'company_site', 'b2b'], queryCount: 10, countries: ['VN', 'TH'], day: 16 },
  { profile_id: 'PRF-0008', profile_name: '波兰储能系统集成商', status: 'draft', version: 1, channels: ['google', 'company_site'], queryCount: 5, countries: ['PL', 'DE'], day: 15 },
  { profile_id: 'PRF-0009', profile_name: '德国工业控制柜连接器采购商 · 二期', status: 'active', version: 2, channels: ['google', 'company_site', 'tradeindia', 'b2b'], queryCount: 16, countries: ['DE', 'PL'], day: 14 },
  { profile_id: 'PRF-0010', profile_name: '意大利新能源充电桩制造商 · 二期', status: 'draft', version: 1, channels: ['google', 'b2b'], queryCount: 6, countries: ['IT'], day: 13 },
  { profile_id: 'PRF-0011', profile_name: '法国医疗设备整机厂 · 二期', status: 'paused', version: 2, channels: ['google', 'company_site'], queryCount: 7, countries: ['FR', 'ES'], day: 12 },
  { profile_id: 'PRF-0012', profile_name: '印度 PCB 与 PCBA 加工厂 · 二期', status: 'active', version: 5, channels: ['tradeindia', 'b2b'], queryCount: 11, countries: ['IN'], day: 11 },
  { profile_id: 'PRF-0013', profile_name: '德国工业控制柜连接器采购商 · 补充批次', status: 'draft', version: 1, channels: ['google'], queryCount: 4, countries: ['DE'], day: 10 },
  { profile_id: 'PRF-0014', profile_name: '美国工业自动化系统集成商 · 高配额版', status: 'active', version: 2, channels: ['google', 'company_site', 'b2b'], queryCount: 13, countries: ['US'], day: 9 }
]

/** 由种子生成演示用的渠道策略（与真实生成结构一致，只是文案更简化） */
function buildSeedChannels(seed: Seed): ChannelSearchStrategy[] {
  const perChannel = Math.max(1, Math.round(seed.queryCount / seed.channels.length))
  return seed.channels.map((channel, channelIndex) => {
    const label = CHANNEL_OPTIONS.find((item) => item.value === channel)?.label ?? channel
    const queries: SearchQuery[] = []
    for (let i = 0; i < perChannel; i += 1) {
      const country = seed.countries[i % seed.countries.length]
      const countryName = en(COUNTRY_EN, country)
      queries.push(
        makeQuery(
          channel === 'company_site'
            ? `site:${COUNTRY_TLD[country] ?? '.com'} ${seed.profile_name.slice(0, 2)} supplier ${i + 1}`
            : `${label.toLowerCase()} ${countryName} supplier query ${channelIndex + 1}-${i + 1}`,
          country,
          i % 3 === 2 && LOCAL_TERMS[country] ? LOCAL_TERMS[country].lang : 'en'
        )
      )
    }
    return {
      channel,
      enabled: channelIndex === 0 ? true : seed.status !== 'paused',
      target_countries: seed.countries,
      strategy_summary: `${label} 渠道：按目标国家与产品线组合检索，覆盖 ${seed.countries.join(' / ')}。`,
      queries
    }
  })
}

const dataset: SearchStrategy[] = seeds.map((seed, index) => ({
  id: `STG-${String(index + 1).padStart(4, '0')}`,
  code: `STG-${String(index + 1).padStart(4, '0')}`,
  profile_id: seed.profile_id,
  profile_name: seed.profile_name,
  status: seed.status,
  version: seed.version,
  channel_strategies: buildSeedChannels(seed),
  created_at: `2026-09-${String(Math.max(1, seed.day - 6)).padStart(2, '0')} 09:30:00`,
  updated_at: `2026-09-${String(seed.day).padStart(2, '0')} 15:40:00`
}))

function nextId(): string {
  return `STG-${String(dataset.length + 1).padStart(4, '0')}`
}

function randomGenerateDelay(): number {
  return GENERATE_MIN + Math.floor(Math.random() * (GENERATE_MAX - GENERATE_MIN))
}

/* -------------------------------------------------------------------------- */
/* 服务端校验                                                                   */
/* -------------------------------------------------------------------------- */

/**
 * 模拟 JOIN CustomerProfile
 * profile_name / profile_enabled 均为 derived 只读字段，每次查询实时取最新值，
 * 存储侧不依赖冗余副本；同时补齐乐观锁基准版本 base_version。
 */
function withProfileMeta(strategy: SearchStrategy, baseVersion?: number): SearchStrategy {
  const meta = getProfileMetaMock(strategy.profile_id)
  return {
    ...strategy,
    profile_name: meta?.profile_name ?? strategy.profile_name,
    profile_enabled: meta?.profile_enabled,
    base_version: baseVersion ?? strategy.version
  }
}

/* -------------------------------------------------------------------------- */
/* 服务方法                                                                     */
/* -------------------------------------------------------------------------- */

/** 列表：服务端筛选 + 分页语义 */
export function listStrategiesMock(query: StrategyQuery): Promise<PageResult<SearchStrategy>> {
  const keyword = query.profile_name?.trim().toLowerCase()

  const filtered = dataset.filter((item) => {
    if (keyword && !item.profile_name.toLowerCase().includes(keyword)) return false
    if (query.profile_id && item.profile_id !== query.profile_id) return false
    if (query.channel && !item.channel_strategies.some((ch) => ch.channel === query.channel)) {
      return false
    }
    if (query.status && item.status !== query.status) return false
    return true
  })

  const start = (query.page - 1) * query.page_size
  return delay({
    list: filtered.slice(start, start + query.page_size).map((item) => withProfileMeta(item)),
    total: filtered.length,
    page: query.page,
    page_size: query.page_size
  })
}

/** 详情 */
export function getStrategyMock(id: string): Promise<SearchStrategy> {
  const target = dataset.find((item) => item.id === id)
  if (!target) return Promise.reject(new Error('搜索策略不存在'))
  return delay(withProfileMeta(structuredClone(target)))
}

/**
 * AI 生成（模拟）
 *
 * 一个画像只维护一套逻辑策略，不产生第二条并行记录：
 *   画像已有策略 → 返回 version + 1 的【预览】，原策略保持不变、不落库；
 *                  真正生效发生在用户点保存（updateStrategyMock）时。
 *   画像无策略   → 落库为 draft v1（草稿不影响生产，可直接持久化）。
 *
 * 核心原则：AI 重新生成 ≠ 自动上线。
 */
export async function generateStrategyMock(profileId: string): Promise<SearchStrategy> {
  const profile = await getProfileMock(profileId)
  const channels = buildChannelStrategies(profile)
  const existing = dataset.find((item) => item.profile_id === profileId)

  if (existing) {
    const preview: SearchStrategy = {
      ...structuredClone(existing),
      version: existing.version + 1,
      channel_strategies: channels
    }
    // base_version = 生成时服务端的当前版本，保存时用于乐观锁比对
    return delay(withProfileMeta(preview, existing.version), randomGenerateDelay())
  }

  const created: SearchStrategy = {
    id: nextId(),
    code: nextId(),
    profile_id: profile.id,
    profile_name: profile.profile_name,
    status: 'draft',
    version: 1,
    channel_strategies: channels,
    created_at: now(),
    updated_at: now()
  }
  dataset.unshift(created)
  return delay(withProfileMeta(structuredClone(created)), randomGenerateDelay())
}

/** 保存：只更新渠道配置与状态，版本与画像归属不变 */
export function updateStrategyMock(
  id: string,
  payload: StrategyUpdatePayload
): Promise<SearchStrategy> {
  const index = dataset.findIndex((item) => item.id === id)
  if (index < 0) return Promise.reject(new Error('搜索策略不存在'))

  const current = dataset[index]

  // 乐观锁：基准版本与服务端当前版本不一致，说明已被他人更新，禁止静默覆盖
  if (current.version !== payload.base_version) {
    return Promise.reject(new ApiError(VERSION_CONFLICT_HINT, 409, STRATEGY_VERSION_CONFLICT))
  }

  // 任何最终状态为 active 的保存都必须通过完整校验；保存草稿允许配置不完整
  if (payload.status === 'active' && !canActivate(payload.channel_strategies)) {
    return Promise.reject(new Error(ACTIVATE_HINT))
  }

  dataset[index] = {
    ...current,
    channel_strategies: payload.channel_strategies,
    status: payload.status,
    // 版本只增不减：来自重新生成预览的提交才会抬升版本
    version: Math.max(current.version, payload.version),
    updated_at: now()
  }
  return delay(withProfileMeta(structuredClone(dataset[index])))
}

/**
 * 重新生成：基于当前画像重新推导，返回 version + 1 的【预览】
 *
 * 不落库：用户点保存前，原 active 策略继续有效、生产配置不被静默覆盖。
 * 历史获客任务记录的 strategy_id / strategy_version 不受影响。
 */
export async function regenerateStrategyMock(id: string): Promise<SearchStrategy> {
  const current = dataset.find((item) => item.id === id)
  if (!current) return Promise.reject(new Error('搜索策略不存在'))

  const profile = await getProfileMock(current.profile_id)
  const preview: SearchStrategy = {
    ...structuredClone(current),
    version: current.version + 1,
    channel_strategies: buildChannelStrategies(profile)
  }
  return delay(withProfileMeta(preview, current.version), randomGenerateDelay())
}

/** 启用 / 暂停 */
export function updateStrategyStatusMock(
  id: string,
  payload: StrategyStatusPayload
): Promise<SearchStrategy> {
  const index = dataset.findIndex((item) => item.id === id)
  if (index < 0) return Promise.reject(new Error('搜索策略不存在'))

  if (payload.status === 'active' && !canActivate(dataset[index].channel_strategies)) {
    return Promise.reject(new Error(ACTIVATE_HINT))
  }

  dataset[index] = { ...dataset[index], status: payload.status, updated_at: now() }
  return delay(withProfileMeta(structuredClone(dataset[index])))
}

/** 顶部统计：正式环境应由后端一次返回，避免为 4 个数字打 4 次列表接口 */
export function getStrategyStatsMock(): Promise<StrategyStats> {
  return delay({
    total: dataset.length,
    active: dataset.filter((item) => item.status === 'active').length,
    draft: dataset.filter((item) => item.status === 'draft').length,
    paused: dataset.filter((item) => item.status === 'paused').length
  })
}
