<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { menuConfig } from '@/router/menu'
import { useAppStore } from '@/stores/app'
import type { MenuGroup } from '@/types/menu'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

const collapsed = computed(() => appStore.sidebarCollapsed)

/** 顶部分组与底部系统分组分开渲染，系统类固定在下方 */
const topMenus = computed<MenuGroup[]>(() => menuConfig.filter((item) => !item.bottom))
const bottomMenus = computed<MenuGroup[]>(() => menuConfig.filter((item) => item.bottom))

/** 当前高亮菜单：详情页通过 meta.activeMenu 指定归属 */
const activeMenu = computed<string>(() => route.meta.activeMenu ?? '')

/** 默认只展开当前路由所属分组 */
const openedGroups = computed<string[]>(() => (route.meta.group ? [route.meta.group] : []))

/** 菜单 key → 路由 path 映射，避免在模板与事件里做路由判断 */
const pathByKey = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  menuConfig.forEach((group) => {
    if (group.path) map[group.key] = group.path
    group.children?.forEach((item) => {
      map[item.key] = item.path
    })
  })
  return map
})

function handleSelect(key: string): void {
  const path = pathByKey.value[key]
  if (path && path !== route.path) {
    router.push(path)
  }
}
</script>

<template>
  <aside class="app-sidebar">
    <div
      class="app-sidebar__brand"
      :class="{ 'is-collapsed': collapsed }"
    >
      <div class="app-sidebar__logo">
        K
      </div>
      <div
        v-show="!collapsed"
        class="app-sidebar__brand-text"
      >
        <div class="app-sidebar__brand-name">
          KULON ELECTRONICS
        </div>
        <div class="app-sidebar__brand-sub">
          AI 自动获客系统
        </div>
      </div>
    </div>

    <el-scrollbar class="app-sidebar__scroll">
      <el-menu
        :default-active="activeMenu"
        :default-openeds="openedGroups"
        :collapse="collapsed"
        :collapse-transition="false"
        unique-opened
        class="app-sidebar__menu"
        @select="handleSelect"
      >
        <template
          v-for="group in topMenus"
          :key="group.key"
        >
          <el-menu-item
            v-if="!group.children"
            :index="group.key"
          >
            <el-icon><component :is="group.icon" /></el-icon>
            <template #title>
              {{ group.title }}
            </template>
          </el-menu-item>

          <el-sub-menu
            v-else
            :index="group.key"
          >
            <template #title>
              <el-icon><component :is="group.icon" /></el-icon>
              <span>{{ group.title }}</span>
            </template>
            <el-menu-item
              v-for="item in group.children"
              :key="item.key"
              :index="item.key"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title>
                {{ item.title }}
              </template>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-scrollbar>

    <div class="app-sidebar__bottom">
      <el-menu
        :default-active="activeMenu"
        :default-openeds="openedGroups"
        :collapse="collapsed"
        :collapse-transition="false"
        class="app-sidebar__menu"
        @select="handleSelect"
      >
        <el-sub-menu
          v-for="group in bottomMenus"
          :key="group.key"
          :index="group.key"
        >
          <template #title>
            <el-icon><component :is="group.icon" /></el-icon>
            <span>{{ group.title }}</span>
          </template>
          <el-menu-item
            v-for="item in group.children"
            :key="item.key"
            :index="item.key"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <template #title>
              {{ item.title }}
            </template>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </div>
  </aside>
</template>

<style scoped>
.app-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--color-sidebar);
}

/* ---------- 品牌区 ---------- */
.app-sidebar__brand {
  display: flex;
  flex: 0 0 var(--header-height);
  gap: 10px;
  align-items: center;
  height: var(--header-height);
  padding: 0 16px;
  background: var(--color-sidebar-deep);
  border-bottom: 1px solid var(--color-sidebar-divider);
}

.app-sidebar__brand.is-collapsed {
  gap: 0;
  justify-content: center;
  padding: 0;
}

.app-sidebar__logo {
  display: flex;
  flex: 0 0 30px;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text-inverse);
  background: var(--color-primary-hover);
  border-radius: var(--radius-base);
}

.app-sidebar__brand-text {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
}

.app-sidebar__brand-name {
  overflow: hidden;
  font-size: var(--font-size-sm);
  font-weight: 600;
  line-height: 18px;
  color: var(--color-text-inverse);
  letter-spacing: 0.4px;
  white-space: nowrap;
}

.app-sidebar__brand-sub {
  font-size: var(--font-size-xs);
  line-height: 16px;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
}

/* ---------- 菜单区 ---------- */
.app-sidebar__scroll {
  flex: 1;
  min-height: 0;
  /* 品牌区与菜单之间留出明确间距 */
  padding-top: 8px;
}

.app-sidebar__bottom {
  flex: 0 0 auto;
  padding-bottom: 8px;
  border-top: 1px solid var(--color-sidebar-divider);
}

.app-sidebar__menu {
  --el-menu-bg-color: transparent;
  --el-menu-text-color: var(--color-sidebar-text);
  --el-menu-hover-bg-color: var(--color-sidebar-hover);
  --el-menu-active-color: var(--color-sidebar-text-active);
  --el-menu-item-height: 44px;
  --el-menu-sub-item-height: 40px;
  --el-menu-base-level-padding: 16px;

  padding: 4px 0;
  border-right: none;
}

.app-sidebar__menu:not(.el-menu--collapse) {
  width: 100%;
}

/* 一级菜单：14px / 500 */
.app-sidebar__menu :deep(.el-menu-item),
.app-sidebar__menu :deep(.el-sub-menu__title) {
  font-size: var(--font-size-base);
  font-weight: 500;
}

/* 二级菜单：13px / 400，统一缩进（Element 按层级写内联 padding，需要覆盖） */
.app-sidebar__menu :deep(.el-sub-menu .el-menu-item) {
  padding-left: 42px !important;
  font-size: var(--font-size-sm);
  font-weight: 400;
}

/* 选中态：品牌绿浅亮底 + 白字，无发光、无渐变 */
.app-sidebar__menu :deep(.el-menu-item.is-active) {
  font-weight: 600;
  color: var(--color-sidebar-text-active);
  background: var(--color-sidebar-active);
}

.app-sidebar__menu :deep(.el-menu-item.is-active:hover) {
  background: var(--color-sidebar-active);
}

/* 展开中的一级分组标题保持常态色，避免与选中项抢视觉 */
.app-sidebar__menu :deep(.el-sub-menu.is-opened > .el-sub-menu__title) {
  color: var(--color-sidebar-text-active);
}

.app-sidebar__menu :deep(.el-sub-menu .el-menu) {
  background: var(--color-sidebar-deep);
}

/* 图标与文字间距统一 */
.app-sidebar__menu:not(.el-menu--collapse) :deep(.el-menu-item .el-icon),
.app-sidebar__menu:not(.el-menu--collapse) :deep(.el-sub-menu__title .el-icon) {
  width: 18px;
  margin-right: 10px;
  font-size: 17px;
}
</style>
