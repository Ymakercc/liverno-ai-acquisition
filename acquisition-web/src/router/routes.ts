/**
 * P0 路由表
 * 业务边界见 CLAUDE.md 第 2、3、4 章。本阶段所有业务页面均为占位页。
 */
import type { RouteRecordRaw } from 'vue-router'

const BasicLayout = () => import('@/layouts/BasicLayout.vue')

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/',
    component: BasicLayout,
    redirect: '/dashboard',
    children: [
      {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: {
          title: '获客总览',
          icon: 'Odometer',
          group: 'workbench',
          requiresAuth: true,
          permission: ['admin', 'sales'],
          activeMenu: 'workbench'
        }
      },
      {
        path: '/profiles',
        name: 'Profiles',
        component: () => import('@/views/profile/index.vue'),
        meta: {
          title: '客户画像',
          icon: 'User',
          group: 'acquisition',
          requiresAuth: true,
          permission: ['admin'],
          activeMenu: 'profiles',
          keepAlive: true
        }
      },
      {
        path: '/search-strategies',
        name: 'SearchStrategies',
        component: () => import('@/views/strategy/index.vue'),
        meta: {
          title: '搜索策略',
          icon: 'Search',
          group: 'acquisition',
          requiresAuth: true,
          permission: ['admin'],
          activeMenu: 'search-strategies',
          keepAlive: true
        }
      },
      {
        path: '/acquisition-tasks',
        name: 'AcquisitionTasks',
        component: () => import('@/views/task/index.vue'),
        meta: {
          title: '获客任务',
          icon: 'List',
          group: 'acquisition',
          requiresAuth: true,
          permission: ['admin'],
          activeMenu: 'acquisition-tasks',
          keepAlive: true
        }
      },
      {
        path: '/acquisition-tasks/:id',
        name: 'AcquisitionTaskDetail',
        component: () => import('@/views/task/detail.vue'),
        meta: {
          title: '获客任务详情',
          icon: 'List',
          group: 'acquisition',
          requiresAuth: true,
          permission: ['admin'],
          activeMenu: 'acquisition-tasks'
        }
      },
      {
        path: '/companies',
        name: 'Companies',
        component: () => import('@/views/company/index.vue'),
        meta: {
          title: '候选企业库',
          icon: 'OfficeBuilding',
          group: 'acquisition',
          requiresAuth: true,
          permission: ['admin', 'sales'],
          activeMenu: 'companies',
          keepAlive: true
        }
      },
      {
        path: '/companies/:id',
        name: 'CompanyDetail',
        component: () => import('@/views/company/detail.vue'),
        meta: {
          title: '企业详情',
          icon: 'OfficeBuilding',
          group: 'acquisition',
          requiresAuth: true,
          permission: ['admin', 'sales'],
          activeMenu: 'companies'
        }
      },
      {
        path: '/contacts',
        name: 'Contacts',
        component: () => import('@/views/contact/index.vue'),
        meta: {
          title: '联系人中心',
          icon: 'Postcard',
          group: 'customer',
          requiresAuth: true,
          permission: ['admin', 'sales'],
          activeMenu: 'contacts',
          keepAlive: true
        }
      },
      {
        path: '/development-pool',
        name: 'DevelopmentPool',
        component: () => import('@/views/customer/development-pool.vue'),
        meta: {
          title: '待开发客户',
          icon: 'Promotion',
          group: 'customer',
          requiresAuth: true,
          permission: ['admin', 'sales'],
          activeMenu: 'development-pool',
          keepAlive: true
        }
      },
      {
        path: '/positive-customers',
        name: 'PositiveCustomers',
        component: () => import('@/views/customer/positive.vue'),
        meta: {
          title: '正向客户',
          icon: 'Star',
          group: 'customer',
          requiresAuth: true,
          permission: ['admin', 'sales'],
          activeMenu: 'positive-customers',
          keepAlive: true
        }
      },
      {
        path: '/opportunities',
        name: 'Opportunities',
        component: () => import('@/views/opportunity/index.vue'),
        meta: {
          title: '商机列表',
          icon: 'Tickets',
          group: 'opportunity',
          requiresAuth: true,
          permission: ['admin', 'sales'],
          activeMenu: 'opportunities',
          keepAlive: true
        }
      },
      {
        path: '/opportunities/:id',
        name: 'OpportunityDetail',
        component: () => import('@/views/opportunity/detail.vue'),
        meta: {
          title: '商机详情',
          icon: 'Tickets',
          group: 'opportunity',
          requiresAuth: true,
          permission: ['admin', 'sales'],
          activeMenu: 'opportunities'
        }
      },
      {
        path: '/logs',
        name: 'Logs',
        component: () => import('@/views/system/logs.vue'),
        meta: {
          title: '运行日志',
          icon: 'Document',
          group: 'system',
          requiresAuth: true,
          permission: ['admin'],
          activeMenu: 'logs',
          keepAlive: true
        }
      },
      {
        path: '/:pathMatch(.*)*',
        name: 'NotFound',
        component: () => import('@/views/error/404.vue'),
        meta: { title: '页面不存在', requiresAuth: true }
      }
    ]
  }
]
