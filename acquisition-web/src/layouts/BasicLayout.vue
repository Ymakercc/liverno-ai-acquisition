<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

/** 桌面端优先：1280 以下自动折叠侧栏（CLAUDE.md 7.6） */
function handleResize(): void {
  appStore.syncByWindowWidth(window.innerWidth)
}

onMounted(() => {
  handleResize()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div
    class="basic-layout"
    :class="{ 'is-collapsed': appStore.sidebarCollapsed }"
  >
    <AppSidebar class="basic-layout__sidebar" />
    <div class="basic-layout__body">
      <AppHeader class="basic-layout__header" />
      <main class="basic-layout__main">
        <RouterView v-slot="{ Component }">
          <component :is="Component" />
        </RouterView>
      </main>
    </div>
  </div>
</template>

<style scoped>
.basic-layout {
  display: flex;
  height: 100%;
  background: var(--color-bg);
}

.basic-layout__sidebar {
  flex: 0 0 var(--sidebar-width);
  width: var(--sidebar-width);
  transition: width var(--layout-transition), flex-basis var(--layout-transition);
}

.basic-layout.is-collapsed .basic-layout__sidebar {
  flex-basis: var(--sidebar-width-collapsed);
  width: var(--sidebar-width-collapsed);
}

.basic-layout__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

.basic-layout__header {
  flex: 0 0 var(--header-height);
}

/* 内容区独立滚动，页面不出现整页滚动条（CLAUDE.md 7.6） */
.basic-layout__main {
  flex: 1;
  min-height: 0;
  padding: var(--page-padding);
  overflow: auto;
}
</style>
