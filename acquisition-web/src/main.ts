import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  Aim,
  ArrowDown,
  ArrowRight,
  Bell,
  Collection,
  DataAnalysis,
  Document,
  Expand,
  Fold,
  List,
  Odometer,
  OfficeBuilding,
  PieChart,
  Plus,
  Postcard,
  Promotion,
  Search,
  Setting,
  Star,
  Suitcase,
  Tickets,
  User
} from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'

/**
 * Element Plus 动态服务组件样式（全局 UI 基础设施）
 *
 * 这四个组件通过命令式 API 调用（ElMessageBox.confirm / ElMessage.success …），
 * 不出现在任何模板里，unplugin-vue-components 扫不到，
 * 一旦调用点用了 `from 'element-plus'` 裸导入就会完全丢失样式。
 * 因此在全局入口统一显式引入，业务页面一律不得自行 import 这些 CSS。
 */
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/notification/style/css'
import 'element-plus/es/components/loading/style/css'

// 全局样式必须放在组件样式之后，保证主题变量覆盖生效
import './styles/index.css'

/**
 * 图标按需注册（线性风格，统一单色）。
 * 菜单配置中的 icon 字段即此处的组件名；新增菜单图标需在这里登记，
 * 禁止改成全量注册 —— 全量会把 ~800KB 图标打进首屏。
 */
const icons = {
  Aim,
  ArrowDown,
  ArrowRight,
  Bell,
  Collection,
  DataAnalysis,
  Document,
  Expand,
  Fold,
  List,
  Odometer,
  OfficeBuilding,
  PieChart,
  Plus,
  Postcard,
  Promotion,
  Search,
  Setting,
  Star,
  Suitcase,
  Tickets,
  User
}

const app = createApp(App)

Object.entries(icons).forEach(([name, component]) => {
  app.component(name, component)
})

app.use(createPinia())
app.use(router)
app.mount('#app')
