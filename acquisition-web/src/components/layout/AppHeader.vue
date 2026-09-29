<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppBreadcrumb from './AppBreadcrumb.vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const appStore = useAppStore()
const userStore = useUserStore()

/** 全局搜索：本阶段仅 UI，不接任何接口 */
const keyword = ref('')

const pageTitle = computed<string>(() => route.meta.title ?? '')

// ElMessage 由 unplugin-auto-import 按需引入，禁止 `from 'element-plus'` 全量导入
function handleCommand(command: string): void {
  // 本阶段不实现登录认证与退出接口（CLAUDE.md 第 11 章）
  ElMessage.info(command === 'logout' ? '退出登录（待接入）' : '个人信息（待接入）')
}
</script>

<template>
  <header class="app-header">
    <div class="app-header__left">
      <el-icon
        class="app-header__collapse"
        @click="appStore.toggleSidebar()"
      >
        <component :is="appStore.sidebarCollapsed ? 'Expand' : 'Fold'" />
      </el-icon>
      <!-- 主标题只出现一次；面包屑作为次级信息置于标题下方 -->
      <div class="app-header__page">
        <h1 class="app-header__title">
          {{ pageTitle }}
        </h1>
        <AppBreadcrumb />
      </div>
    </div>

    <div class="app-header__right">
      <el-input
        v-model="keyword"
        class="app-header__search"
        placeholder="搜索企业 / 联系人"
        clearable
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-badge
        :value="0"
        :show-zero="false"
        class="app-header__badge"
      >
        <el-icon class="app-header__icon">
          <Bell />
        </el-icon>
      </el-badge>

      <el-dropdown
        trigger="click"
        @command="handleCommand"
      >
        <div class="app-header__user">
          <el-avatar
            :size="28"
            class="app-header__avatar"
          >
            {{ userStore.currentUser.name.charAt(0) }}
          </el-avatar>
          <span class="app-header__username">{{ userStore.currentUser.name }}</span>
          <el-icon class="app-header__arrow">
            <ArrowDown />
          </el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              个人信息
            </el-dropdown-item>
            <el-dropdown-item
              command="logout"
              divided
            >
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 var(--page-padding);
  background: var(--color-card);
  border-bottom: 1px solid var(--color-border);
}

.app-header__left {
  display: flex;
  gap: 14px;
  align-items: center;
  min-width: 0;
}

.app-header__page {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
}

.app-header__collapse {
  font-size: 18px;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.app-header__collapse:hover {
  color: var(--color-primary);
}

.app-header__title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
  line-height: 22px;
  color: var(--color-text-primary);
  white-space: nowrap;
}

.app-header__right {
  display: flex;
  gap: 16px;
  align-items: center;
}

.app-header__search {
  width: 220px;
}

.app-header__icon {
  font-size: 18px;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.app-header__icon:hover {
  color: var(--color-primary);
}

.app-header__user {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 4px 6px;
  cursor: pointer;
  border-radius: var(--radius-base);
}

.app-header__user:hover {
  background: var(--color-bg);
}

.app-header__avatar {
  background: var(--color-primary);
}

.app-header__username {
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
}

.app-header__arrow {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* 1280 以下收起搜索框，保证 Header 不拥挤 */
@media (max-width: 1279px) {
  .app-header__search {
    display: none;
  }
}
</style>
