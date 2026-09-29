<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { menuConfig } from '@/router/menu'

const route = useRoute()

/**
 * 面包屑只展示「祖先路径」，不重复当前页面标题
 * —— 页面标题已由 Header 主标题承担，避免同一个名字出现两次。
 *   列表页：获客中心
 *   详情页：获客中心 / 候选企业库
 */
const items = computed<string[]>(() => {
  const group = menuConfig.find((item) => item.key === route.meta.group)
  if (!group) return []

  const trail: string[] = [group.title]
  const parentItem = group.children?.find((item) => item.key === route.meta.activeMenu)
  if (parentItem && parentItem.title !== route.meta.title) {
    trail.push(parentItem.title)
  }
  return trail
})
</script>

<template>
  <nav
    v-if="items.length"
    class="app-breadcrumb"
  >
    <template
      v-for="(item, index) in items"
      :key="item"
    >
      <span
        v-if="index > 0"
        class="app-breadcrumb__sep"
      >/</span>
      <span class="app-breadcrumb__item">{{ item }}</span>
    </template>
  </nav>
</template>

<style scoped>
.app-breadcrumb {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: var(--font-size-xs);
  line-height: 16px;
  color: var(--color-text-secondary);
}

.app-breadcrumb__sep {
  color: var(--color-text-placeholder);
}
</style>
