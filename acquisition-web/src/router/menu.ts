/**
 * 侧边栏菜单配置（P0）
 * 菜单与路由解耦：Sidebar 只消费此配置，不做路由判断。
 * 新增页面时先加路由，再决定是否在此暴露菜单入口。
 *
 * 关于「数据中心」：
 * P0 阶段的数据能力（每日目标完成、核心漏斗、各环节数量、链路是否正常）
 * 已全部由「工作台 → /dashboard → 获客总览」承担，
 * 再保留一个数据中心入口会造成两个菜单指向同一页面、职责重叠。
 * 因此 P0 只移除菜单入口，/dashboard 路由与页面能力保持不变；
 * 待 P1/P2 出现真正独立的数据分析能力（趋势、渠道对比、转化率、同比环比、ROI）后再恢复。
 */
import type { MenuGroup } from '@/types/menu'

export const menuConfig: MenuGroup[] = [
  {
    key: 'workbench',
    title: '工作台',
    icon: 'Odometer',
    path: '/dashboard'
  },
  {
    key: 'acquisition',
    title: '获客中心',
    icon: 'Aim',
    children: [
      { key: 'profiles', title: '客户画像', path: '/profiles', icon: 'User' },
      { key: 'search-strategies', title: '搜索策略', path: '/search-strategies', icon: 'Search' },
      { key: 'acquisition-tasks', title: '获客任务', path: '/acquisition-tasks', icon: 'List' },
      { key: 'companies', title: '候选企业库', path: '/companies', icon: 'OfficeBuilding' }
    ]
  },
  {
    key: 'customer',
    title: '客户中心',
    icon: 'Collection',
    children: [
      { key: 'contacts', title: '联系人中心', path: '/contacts', icon: 'Postcard' },
      { key: 'development-pool', title: '待开发客户', path: '/development-pool', icon: 'Promotion' },
      { key: 'positive-customers', title: '正向客户', path: '/positive-customers', icon: 'Star' }
    ]
  },
  {
    key: 'opportunity',
    title: '商机管理',
    icon: 'Suitcase',
    children: [{ key: 'opportunities', title: '商机列表', path: '/opportunities', icon: 'Tickets' }]
  },
  {
    key: 'system',
    title: '系统',
    icon: 'Setting',
    bottom: true,
    children: [{ key: 'logs', title: '运行日志', path: '/logs', icon: 'Document' }]
  }
]
