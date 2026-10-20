import { createApp } from 'vue'
import App from './App.vue'
import pinia from './stores'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// 必须在 element-plus 的样式之后导入，同特异性下才能覆盖组件外观（分页器等）
import './styles/anime-theme.scss'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { useAuthStore } from './stores/auth'

const app = createApp(App)

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)

// 初始化认证状态（从 localStorage 恢复用户信息）
const authStore = useAuthStore()
authStore.initAuth()

app.use(router)
app.use(ElementPlus)
app.mount('#app')
