import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '@/views/LoginView.vue'
import RegisterView from '@/views/RegisterView.vue'
import Layout from '@/components/Layout.vue'
import HomeView from '@/views/HomeView.vue'
import ProfileView from '@/views/ProfileView.vue'
import WatchHistoryView from '@/views/WatchHistoryView.vue'
import AnimeDetailView from '@/views/AnimeDetailView.vue'
import SeasonalAnimeView from '@/views/SeasonalAnimeView.vue'
import NewsListView from '@/views/NewsListView.vue'
import NewsDetailView from '@/views/NewsDetailView.vue'
import ChatView from '@/views/ChatView.vue'
import CharacterView from '@/views/CharacterView.vue'
import CharacterDetailView from '@/views/CharacterDetailView.vue'
import FavoriteCharactersView from '@/views/FavoriteCharactersView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: LoginView,
      meta: { requiresAuth: false } // 不需要登录
    },
    {
      path: '/register',
      name: 'Register',
      component: RegisterView,
      meta: { requiresAuth: false } // 不需要登录
    },
    {
      path: '/',
      component: Layout,
      meta: { requiresAuth: true }, // 需要登录
      children: [
        {
          path: '',
          name: 'Home',
          component: HomeView
        },
        {
          path: 'profile',
          name: 'Profile',
          component: ProfileView
        },
        {
          path: 'watch-history',
          name: 'WatchHistory',
          component: WatchHistoryView
        },
        {
          path: 'anime/:id',
          name: 'AnimeDetail',
          component: AnimeDetailView,
          props: true
        },
        {
          path: 'seasonal',
          name: 'SeasonalAnime',
          component: SeasonalAnimeView
        },
        {
          path: 'news',
          name: 'News',
          component: NewsListView
        },
        {
          path: 'news/:id',
          name: 'NewsDetail',
          component: NewsDetailView,
          props: true
        },
        {
          path: 'chat',
          name: 'Chat',
          component: ChatView
        },
        {
          path: 'characters',
          name: 'Characters',
          component: CharacterView
        },
        {
          path: 'characters/:id',
          name: 'CharacterDetail',
          component: CharacterDetailView,
          props: true
        },
        {
          path: 'favorite-characters',
          name: 'FavoriteCharacters',
          component: FavoriteCharactersView
        }
        // TODO: 后续添加其他子路由
      ]
    }
  ]
})

// 全局前置守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('accessToken')
  
  // 检查目标路由是否需要登录
  if (to.meta.requiresAuth) {
    // 需要登录但未登录，跳转到登录页
    if (!token) {
      next({
        path: '/login',
        query: { redirect: to.fullPath } // 保存目标路径，登录后可以跳回来
      })
    } else {
      // 有token，允许访问（如果token无效，会在API请求时被拦截器处理）
      next()
    }
  } else {
    // 不需要登录的路由（登录/注册），直接放行
    next()
  }
})

export default router
