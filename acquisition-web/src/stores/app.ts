/**
 * 全局布局状态
 * CLAUDE.md 7.6：侧栏折叠状态存 localStorage，用户手动操作优先于窗口自动折叠。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'app:sidebar-collapsed'
/** 低于该宽度自动折叠侧栏 */
const AUTO_COLLAPSE_WIDTH = 1280

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref<boolean>(localStorage.getItem(STORAGE_KEY) === '1')
  /** 用户本次会话是否手动操作过折叠按钮 */
  const userToggled = ref(false)

  function setCollapsed(value: boolean): void {
    sidebarCollapsed.value = value
    localStorage.setItem(STORAGE_KEY, value ? '1' : '0')
  }

  /** Header 折叠按钮 */
  function toggleSidebar(): void {
    userToggled.value = true
    setCollapsed(!sidebarCollapsed.value)
  }

  /** 窗口尺寸变化触发；手动操作过之后不再自动接管 */
  function syncByWindowWidth(width: number): void {
    if (userToggled.value) return
    setCollapsed(width < AUTO_COLLAPSE_WIDTH)
  }

  return { sidebarCollapsed, userToggled, toggleSidebar, setCollapsed, syncByWindowWidth }
})
