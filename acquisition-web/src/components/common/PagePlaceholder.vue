<script setup lang="ts">
/**
 * 业务页面占位组件
 * 第一阶段只搭框架，各业务页面用它显示「页面名称 + 页面职责」，
 * 后续按 P0 顺序逐个替换为真实页面。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

interface Props {
  /** 页面职责说明（一句话） */
  description: string
  /** 页面名称，默认取路由 meta.title */
  title?: string
  /** 本阶段未实现的能力，列出来避免误解为已完成 */
  todo?: string[]
}

const props = withDefaults(defineProps<Props>(), { title: '', todo: () => [] })

const route = useRoute()
const pageTitle = computed<string>(() => props.title || route.meta.title || '')
</script>

<template>
  <section class="page-placeholder app-card">
    <header class="page-placeholder__head">
      <h2 class="page-placeholder__title">
        {{ pageTitle }}
      </h2>
      <el-tag
        size="small"
        type="info"
        effect="plain"
      >
        P0 占位页
      </el-tag>
    </header>

    <p class="page-placeholder__desc">
      {{ description }}
    </p>

    <ul
      v-if="todo.length"
      class="page-placeholder__todo"
    >
      <li
        v-for="item in todo"
        :key="item"
      >
        {{ item }}
      </li>
    </ul>

    <footer class="page-placeholder__meta">
      <span>路由：{{ route.path }}</span>
      <span v-if="route.meta.group">分组：{{ route.meta.group }}</span>
    </footer>
  </section>
</template>

<style scoped>
.page-placeholder {
  padding: var(--space-xl);
}

.page-placeholder__head {
  display: flex;
  gap: 10px;
  align-items: center;
}

.page-placeholder__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
}

.page-placeholder__desc {
  max-width: 900px;
  margin: 12px 0 0;
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
}

.page-placeholder__todo {
  margin: 16px 0 0;
  padding-left: 18px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.page-placeholder__todo li {
  margin-bottom: 4px;
}

.page-placeholder__meta {
  display: flex;
  gap: 20px;
  margin-top: 24px;
  padding-top: 16px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  border-top: 1px solid var(--color-border-light);
}
</style>
