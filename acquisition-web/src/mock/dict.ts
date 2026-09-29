/**
 * 业务字典（当前为 Mock）
 * 后端提供字典接口后，整体迁移到 src/api/dict.ts 并进 Pinia 缓存（CLAUDE.md 8.4），
 * 页面只消费 Option[]，届时无需改动。
 * 注意：渠道、国家等字段一律走字典渲染，禁止在页面写死（CLAUDE.md 9.10）。
 */
import type { Option } from '@/types/common'
import type { ProfilePriority } from '@/types/profile'
import type { StrategyStatus } from '@/types/strategy'
import type { TaskStatus } from '@/types/task'
import type { CompanyGrade, RelevanceFilter } from '@/types/company'
import type { ContactSourceType, EmailVerificationStatus } from '@/types/contact'

/** 目标行业 */
export const INDUSTRY_OPTIONS: Option[] = [
  { label: '连接器 / 线束', value: 'connector_harness' },
  { label: 'PCB / PCBA', value: 'pcb_pcba' },
  { label: '电源模块', value: 'power_module' },
  { label: '工业自动化', value: 'industrial_automation' },
  { label: '汽车电子', value: 'automotive_electronics' },
  { label: '医疗设备', value: 'medical_device' },
  { label: '新能源储能', value: 'energy_storage' },
  { label: '消费电子', value: 'consumer_electronics' },
  { label: '安防监控', value: 'security_surveillance' },
  { label: '通信设备', value: 'telecom_equipment' }
]

/** 目标地区 */
export const REGION_OPTIONS: Option[] = [
  { label: '西欧', value: 'western_europe' },
  { label: '中东欧', value: 'central_eastern_europe' },
  { label: '北美', value: 'north_america' },
  { label: '南美', value: 'south_america' },
  { label: '中东', value: 'middle_east' },
  { label: '南亚', value: 'south_asia' },
  { label: '东南亚', value: 'southeast_asia' },
  { label: '东亚', value: 'east_asia' },
  { label: '非洲', value: 'africa' },
  { label: '大洋洲', value: 'oceania' }
]

/** 目标国家：显示中文名，value 为 ISO 3166-1 alpha-2 代码 */
export const COUNTRY_OPTIONS: Option[] = [
  { label: '德国', value: 'DE' },
  { label: '意大利', value: 'IT' },
  { label: '法国', value: 'FR' },
  { label: '西班牙', value: 'ES' },
  { label: '荷兰', value: 'NL' },
  { label: '波兰', value: 'PL' },
  { label: '英国', value: 'GB' },
  { label: '土耳其', value: 'TR' },
  { label: '美国', value: 'US' },
  { label: '加拿大', value: 'CA' },
  { label: '墨西哥', value: 'MX' },
  { label: '巴西', value: 'BR' },
  { label: '阿联酋', value: 'AE' },
  { label: '印度', value: 'IN' },
  { label: '越南', value: 'VN' },
  { label: '泰国', value: 'TH' },
  { label: '马来西亚', value: 'MY' },
  { label: '印度尼西亚', value: 'ID' },
  { label: '日本', value: 'JP' },
  { label: '韩国', value: 'KR' },
  { label: '澳大利亚', value: 'AU' }
]

/** 企业类型 */
export const COMPANY_TYPE_OPTIONS: Option[] = [
  { label: '制造商 / OEM', value: 'oem' },
  { label: 'ODM', value: 'odm' },
  { label: '品牌商', value: 'brand' },
  { label: '经销商 / 代理商', value: 'distributor' },
  { label: '贸易公司', value: 'trading' },
  { label: '系统集成商', value: 'system_integrator' },
  { label: 'EMS 代工厂', value: 'ems' },
  { label: '终端用户', value: 'end_user' }
]

/** 企业规模（员工数区间） */
export const COMPANY_SIZE_OPTIONS: Option[] = [
  { label: '1 - 10 人', value: '1-10' },
  { label: '11 - 50 人', value: '11-50' },
  { label: '51 - 200 人', value: '51-200' },
  { label: '201 - 500 人', value: '201-500' },
  { label: '501 - 1000 人', value: '501-1000' },
  { label: '1000 人以上', value: '1000+' },
  { label: '不限', value: 'any' }
]

/** 匹配产品线 */
export const PRODUCT_LINE_OPTIONS: Option[] = [
  { label: '端子连接器', value: 'terminal_connector' },
  { label: '线束组件', value: 'wire_harness' },
  { label: 'PCB 连接器', value: 'pcb_connector' },
  { label: '电源连接器', value: 'power_connector' },
  { label: '防水连接器', value: 'waterproof_connector' },
  { label: '射频连接器', value: 'rf_connector' },
  { label: '排针 / 排母', value: 'pin_header' },
  { label: 'FFC / FPC', value: 'ffc_fpc' }
]

/** 目标应用场景 */
export const APPLICATION_SCENARIO_OPTIONS: Option[] = [
  { label: '工业控制柜', value: 'industrial_cabinet' },
  { label: '新能源充电桩', value: 'ev_charger' },
  { label: '储能系统', value: 'energy_storage_system' },
  { label: '伺服驱动', value: 'servo_drive' },
  { label: '医疗影像设备', value: 'medical_imaging' },
  { label: '车载电子', value: 'in_vehicle' },
  { label: '智能家居', value: 'smart_home' },
  { label: 'LED 照明', value: 'led_lighting' },
  { label: '安防摄像机', value: 'security_camera' },
  { label: '通信基站', value: 'telecom_base_station' }
]

/** 目标联系人角色 */
export const TARGET_ROLE_OPTIONS: Option[] = [
  { label: '采购经理', value: 'purchasing_manager' },
  { label: '采购工程师', value: 'purchasing_engineer' },
  { label: '研发工程师', value: 'rd_engineer' },
  { label: '硬件工程师', value: 'hardware_engineer' },
  { label: '供应链经理', value: 'supply_chain_manager' },
  { label: '技术总监', value: 'cto' },
  { label: '总经理', value: 'general_manager' },
  { label: '创始人', value: 'founder' }
]

/**
 * 搜索渠道（P0）
 * 渠道必须可扩展：页面一律按此字典渲染，禁止在组件内写死 channel 判断。
 * 未来的 LinkedIn / Facebook / Instagram 等在此追加即可，本期不实现。
 */
export const CHANNEL_OPTIONS: Option[] = [
  { label: 'Google', value: 'google' },
  { label: '企业官网', value: 'company_site' },
  { label: 'TradeIndia', value: 'tradeindia' },
  { label: '其他 B2B 平台', value: 'b2b' }
]

/** 邮箱验证状态：只有 valid 允许进入自动营销（CLAUDE.md 9.4） */
export const EMAIL_STATUS_OPTIONS: Option<EmailVerificationStatus>[] = [
  { label: '待验证', value: 'pending' },
  { label: '验证通过', value: 'valid' },
  { label: '验证失败', value: 'invalid' },
  { label: 'Catch-All', value: 'catch_all' },
  { label: '无法确定', value: 'unknown' }
]

/** 联系人来源：同一联系人可有多个来源，禁止在 Contact 上写死单一来源 */
export const CONTACT_SOURCE_OPTIONS: Option<ContactSourceType>[] = [
  { label: 'Apollo', value: 'apollo' },
  { label: '企业官网', value: 'website' },
  { label: 'B2B 平台', value: 'b2b' },
  { label: '其他', value: 'other' }
]

/** AI 相关性判断（CLAUDE.md 9.3：is_relevant + grade + reason） */
export const RELEVANCE_OPTIONS: Option<RelevanceFilter>[] = [
  { label: '相关', value: 'relevant' },
  { label: '不相关', value: 'not_relevant' },
  { label: '待分析', value: 'pending' },
  { label: '分析失败', value: 'failed' }
]

/** AI 等级：仅在 is_relevant = true 时有意义，只表示优先级 */
export const GRADE_OPTIONS: Option<CompanyGrade>[] = [
  { label: 'A', value: 'A' },
  { label: 'B', value: 'B' },
  { label: 'C', value: 'C' }
]

/** 获客任务状态 */
export const TASK_STATUS_OPTIONS: Option<TaskStatus>[] = [
  { label: '待执行', value: 'pending' },
  { label: '执行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '失败', value: 'failed' }
]

/**
 * 搜索 Query 语言（ISO 639-1）
 * 由 AI 在生成每条 Query 时决定，允许同一国家产出多语言 Query；
 * 前端仅提供人工修改能力，禁止按国家硬编码推导语言。
 */
export const LANGUAGE_OPTIONS: Option[] = [
  { label: 'English (en)', value: 'en' },
  { label: 'Deutsch (de)', value: 'de' },
  { label: 'Italiano (it)', value: 'it' },
  { label: 'Français (fr)', value: 'fr' },
  { label: 'Español (es)', value: 'es' },
  { label: 'Nederlands (nl)', value: 'nl' },
  { label: 'Polski (pl)', value: 'pl' },
  { label: 'Türkçe (tr)', value: 'tr' },
  { label: 'Português (pt)', value: 'pt' },
  { label: '日本語 (ja)', value: 'ja' },
  { label: '한국어 (ko)', value: 'ko' },
  { label: 'Tiếng Việt (vi)', value: 'vi' }
]

/** 搜索策略状态 */
export const STRATEGY_STATUS_OPTIONS: Option<StrategyStatus>[] = [
  { label: '草稿', value: 'draft' },
  { label: '启用', value: 'active' },
  { label: '暂停', value: 'paused' }
]

/** 优先级 */
export const PRIORITY_OPTIONS: Option<ProfilePriority>[] = [
  { label: '高', value: 'high' },
  { label: '中', value: 'medium' },
  { label: '低', value: 'low' }
]

/** 启用状态 */
export const STATUS_OPTIONS: Option<'enabled' | 'disabled'>[] = [
  { label: '启用', value: 'enabled' },
  { label: '暂停', value: 'disabled' }
]

/** 取单个字典值的显示名，取不到时回退原值，避免界面出现空白 */
export function labelOf<T extends string>(options: Option<T>[], value: T | undefined): string {
  if (!value) return '-'
  return options.find((item) => item.value === value)?.label ?? value
}

/** 取一组字典值的显示名 */
export function labelsOf<T extends string>(options: Option<T>[], values: T[] | undefined): string[] {
  if (!values?.length) return []
  return values.map((value) => labelOf(options, value))
}
