<template>
  <div class="common-layout">
    <el-container>
      <!-- 1. 顶部 Header -->
      <el-header class="layout-header">
        <div class="header-content">
          <div class="header-left">
            <h2 class="site-logo">
              <span class="logo-text colorful-gradient">浅上小站</span>
              <span class="logo-decoration">✨</span>
            </h2>
            <!-- 清除缓存按钮 -->
            <el-button
              size="small"
              :icon="Delete"
              @click="handleClearCache"
              class="clear-cache-btn"
            >
              清除缓存
            </el-button>
          </div>
          <div class="header-center">
            <div class="search-wrapper">
              <el-input
                v-model="searchQuery"
                placeholder="请搜索游戏名称或关键词"
                class="search-input"
                :prefix-icon="Search"
                clearable
                @keyup.enter="handleSearch"
              />
              <span class="enter-hint">Enter</span>
            </div>
          </div>
          <div class="header-right">
            <!-- 未登录状态 -->
            <template v-if="!isLoggedIn">
              <el-button type="primary" plain>登录</el-button>
              <el-button type="primary">注册</el-button>
            </template>
            
            <!-- 已登录状态 - 用户信息 -->
            <template v-else>
              <el-dropdown trigger="click" @command="handleCommand">
                <div class="user-info">
                  <el-avatar 
                    :size="36" 
                    class="user-avatar"
                    :src="userInfo?.avatar || undefined"
                  >
                    <el-icon><User /></el-icon>
                  </el-avatar>
                  <span class="user-name">{{ displayName }}</span>
                </div>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="profile">
                      <el-icon><User /></el-icon>
                      个人信息
                    </el-dropdown-item>
                    <el-dropdown-item command="settings">
                      <el-icon><Setting /></el-icon>
                      设置
                    </el-dropdown-item>
                    <el-dropdown-item divided command="logout">
                      <el-icon><SwitchButton /></el-icon>
                      退出登录
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </div>
        </div>
      </el-header>

      <!-- 下方容器：侧边栏 + 主内容 -->
      <el-container>
        <!-- 2. 左侧侧边栏 Aside -->
        <el-aside width="240px" class="layout-aside">
          <div class="aside-content">
            <div class="aside-menu">
              <el-menu :default-active="activeMenu" class="aside-menu-list" @select="handleMenuSelect">
                <el-menu-item index="/">
                  <el-icon><House /></el-icon>
                  <span>首页</span>
                </el-menu-item>
                <el-menu-item index="/seasonal">
                  <el-icon><Calendar /></el-icon>
                  <span>当季新番</span>
                </el-menu-item>
                <el-menu-item index="/news">
                  <el-icon><Document /></el-icon>
                  <span>动漫资讯</span>
                </el-menu-item>
                <el-menu-item index="/chat">
                  <el-icon><ChatDotRound /></el-icon>
                  <span>AI助手</span>
                </el-menu-item>
                <el-menu-item index="/characters">
                  <el-icon><Collection /></el-icon>
                  <span>角色</span>
                </el-menu-item>
                <el-menu-item index="/favorite-characters">
                  <el-icon><Star /></el-icon>
                  <span>喜欢</span>
                </el-menu-item>
                <el-menu-item index="/watch-history">
                  <el-icon><Clock /></el-icon>
                  <span>历史</span>
                </el-menu-item>
              </el-menu>
            </div>

            <!-- 知识库入口（导航栏底部） -->
            <div class="aside-knowledge">
              <div class="kb-entry" @click="knowledgeModalVisible = true">
                <span class="kb-entry-icon">📚</span>
                <div class="kb-entry-text">
                  <span class="kb-entry-title">知识库</span>
                  <span class="kb-entry-desc">上传资料给 AI</span>
                </div>
                <span class="kb-entry-spark">✨</span>
              </div>
            </div>
          </div>
        </el-aside>

        <!-- 右侧容器：Main + Footer -->
        <el-container class="layout-right-container">
          <!-- 3. 主内容区 Main -->
          <el-main class="layout-main">
            <div class="main-background">
              <img src="@/assets/hinata.webp" alt="background" class="bg-image" loading="eager" />
              <div class="bg-overlay"></div>
            </div>
            <div class="main-content">
              <!-- 内容将在这里渲染 -->
              <router-view />
            </div>
          </el-main>

          <!-- 4. 底部 Footer -->
          <el-footer class="layout-footer">
            <div class="footer-inner">
              <span class="footer-petal">🌸</span>
              <p class="footer-text">
                © 2026
                <span class="footer-brand">Gal Wiki</span>
                <span class="footer-dot">·</span>
                用热爱搭建的二次元小站
              </p>
              <span class="footer-spark">✦</span>
            </div>
          </el-footer>
        </el-container>
      </el-container>
    </el-container>

    <!-- 知识库弹窗（RAG 上传入口） -->
    <KnowledgeBaseModal v-model="knowledgeModalVisible" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Search, Clock, User, Setting, SwitchButton, House, Calendar, ChatDotRound, Collection, Delete, Star, Document } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { clearAllCache } from '@/api/anime'
import KnowledgeBaseModal from '@/components/KnowledgeBaseModal.vue'

const router = useRouter()
const route = useRoute()
const searchQuery = ref('')

// 知识库弹窗显隐
const knowledgeModalVisible = ref(false)

// 根据当前路由设置激活的菜单项
const activeMenu = computed(() => {
  return route.path
})

// 使用 Auth Store
const authStore = useAuthStore()

// 用户是否已登录
const isLoggedIn = computed(() => authStore.isLoggedIn)

// 用户信息
const userInfo = computed(() => authStore.userInfo)

// 用户昵称（优先显示昵称，其次用户名）
const displayName = computed(() => {
  if (!userInfo.value) return '用户'
  return userInfo.value.nickname || userInfo.value.username
})

// 组件挂载时，如果有 Token 但没有用户信息，则从后端获取
// 注意：Token 过期的处理已统一在 request.ts 的响应拦截器中处理
onMounted(async () => {
  if (authStore.token && !authStore.userInfo) {
    console.log('检测到 Token 但无用户信息，正在获取...')
    const result = await authStore.fetchUserInfo()
    // 如果获取失败，request.ts 的拦截器会自动处理跳转，这里不需要额外处理
    if (!result.success) {
      console.log('获取用户信息失败，等待拦截器处理跳转')
    }
  }
})

// 处理下拉菜单命令
const handleCommand = (command: string) => {
  switch (command) {
    case 'profile':
      // 跳转到个人信息页
      router.push('/profile')
      break
    case 'settings':
      // TODO: 跳转到设置页
      ElMessage.info('设置功能开发中')
      break
    case 'logout':
      handleLogout()
      break
  }
}

// 处理登出
const handleLogout = () => {
  authStore.logout()
  ElMessage.success('已退出登录')
  // 跳转到登录页
  router.push('/login')
}

// 处理菜单选择
const handleMenuSelect = (index: string) => {
  if (index !== route.path) {
    router.push(index)
  }
}

// 提供搜索查询给子组件
provide('searchQuery', searchQuery)

// 处理搜索（点击搜索按钮或按Enter键）
const handleSearch = () => {
  // 触发搜索事件，通知子组件
  window.dispatchEvent(new CustomEvent('searchChange', { detail: searchQuery.value }))
}

// 清除所有缓存
const handleClearCache = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清除所有缓存吗？此操作不可恢复。',
      '警告',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    // 检查是否有token
    if (!authStore.token) {
      ElMessage.error('请先登录')
      return
    }
    
    console.log('[清除缓存] 开始调用API...')
    
    // 调用后端API清除缓存（使用axios实例，自动请求到8081端口）
    const result = await clearAllCache()
    
    console.log('[清除缓存] 响应数据:', result)
    ElMessage.success(`缓存清除成功！共删除 ${result.data?.deletedCount || 0} 个key`)
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('[清除缓存] 异常:', error)
      ElMessage.error(error.message || '清除缓存失败')
    }
  }
}
</script>

<style scoped lang="scss">
// ==================== 二次元主题变量 ====================
$sakura: #ff8fb8;
$sakura-soft: #ffd0e2;
$violet: #9b7bff;
$violet-deep: #7b5cf0;
$sky: #78d2ff;
$ink: #3f3555;
$ink-soft: #7b6f96;
$header-h: 60px;
$aside-w: 240px;
$footer-h: 50px;
$glass-line: rgba(255, 255, 255, 0.85);
$gradient-brand: linear-gradient(120deg, $sakura 0%, $violet 55%, $sky 100%);

// 玻璃拟态面板：淡紫粉渐变 + 背景虚化 + 白色内描边
@mixin glass-panel($alpha: 0.72) {
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, $alpha) 0%,
    rgba(255, 244, 250, $alpha * 0.92) 45%,
    rgba(243, 246, 255, $alpha) 100%
  );
  -webkit-backdrop-filter: blur(18px) saturate(170%);
  backdrop-filter: blur(18px) saturate(170%);
  border: 1px solid $glass-line;
}

.common-layout {
  height: 100vh;
  width: 100%;
  // 整页铺一层柔和的樱花粉 -> 紫罗兰 -> 天蓝底，玻璃面板压在上面才有层次
  background:
    radial-gradient(1100px 520px at 6% -10%, rgba(255, 178, 208, 0.58), transparent 62%),
    radial-gradient(900px 520px at 98% 2%, rgba(155, 123, 255, 0.34), transparent 60%),
    radial-gradient(760px 460px at 62% 104%, rgba(120, 210, 255, 0.32), transparent 66%),
    linear-gradient(160deg, #fdf6fb 0%, #f6f2ff 48%, #f1f8ff 100%);

  // ==================== 顶部 Header ====================
  .layout-header {
    position: relative;
    height: $header-h;
    padding: 0;
    @include glass-panel(0.78);
    border: none;
    box-shadow: 0 6px 22px rgba(123, 92, 240, 0.1);
    z-index: 20;

    // 底部渐变色发丝线，替代生硬的灰色边框
    &::after {
      content: '';
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      height: 2px;
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(255, 143, 184, 0.75) 22%,
        rgba(155, 123, 255, 0.8) 52%,
        rgba(120, 210, 255, 0.75) 78%,
        transparent 100%
      );
      opacity: 0.9;
      pointer-events: none;
    }

    .header-content {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 22px;

      .header-left {
        display: flex;
        align-items: center;
        gap: 16px;

        .site-logo {
          margin: 0;
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 1.8rem;
          font-weight: 700;

          .logo-text {
            &.colorful-gradient {
              background: linear-gradient(
                90deg,
                #ff8fb8 0%,
                #c99bff 28%,
                #9b7bff 52%,
                #78d2ff 76%,
                #ff8fb8 100%
              );
              -webkit-background-clip: text;
              -webkit-text-fill-color: transparent;
              background-clip: text;
              font-style: italic;
              letter-spacing: 2px;
              animation: gradient-shift 6s ease infinite;
              background-size: 220% auto;
              filter: drop-shadow(0 2px 8px rgba(155, 123, 255, 0.28));
            }
          }

          .logo-decoration {
            font-size: 1.2rem;
            animation: sparkle 2.4s ease-in-out infinite;
          }
        }

        // 清除缓存：做成粉色糖果按钮，不再用刺眼的 danger 红
        .clear-cache-btn {
          border-radius: 999px;
          padding: 7px 15px;
          font-weight: 500;
          color: #c2557f;
          background: linear-gradient(120deg, rgba(255, 143, 184, 0.18), rgba(255, 208, 226, 0.3));
          border: 1px solid rgba(255, 143, 184, 0.45);
          transition: all 0.25s ease;

          &:hover {
            color: #fff;
            background: linear-gradient(120deg, $sakura, $violet);
            border-color: transparent;
            box-shadow: 0 6px 16px rgba(255, 143, 184, 0.42);
            transform: translateY(-1px);
          }

          &:active {
            transform: translateY(0);
          }
        }
      }

      .header-center {
        flex: 1;
        max-width: 600px;
        margin: 0 40px;

        // 渐变描边药丸搜索框：内部白底、外圈樱花->紫->天蓝
        .search-wrapper {
          position: relative;
          display: flex;
          align-items: center;
          border-radius: 999px;
          border: 1.5px solid transparent;
          background:
            linear-gradient(rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.95)) padding-box,
            $gradient-brand border-box;
          box-shadow: 0 6px 18px rgba(155, 123, 255, 0.16);
          transition: box-shadow 0.28s ease, transform 0.28s ease;

          &:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 24px rgba(155, 123, 255, 0.22);
          }

          &:focus-within {
            box-shadow:
              0 0 0 4px rgba(155, 123, 255, 0.15),
              0 10px 26px rgba(255, 143, 184, 0.24);
          }

          .search-input {
            flex: 1;
            border: none;

            :deep(.el-input__wrapper) {
              box-shadow: none !important;
              background: transparent;
              padding-left: 16px;
              padding-right: 6px;
              border-radius: 999px 0 0 999px;
            }

            :deep(.el-input__inner) {
              font-size: 14px;
              color: $ink;

              &::placeholder {
                color: #b3a8c9;
              }
            }

            :deep(.el-input__prefix) {
              color: $violet;

              .el-icon {
                font-size: 18px;
              }
            }

            :deep(.el-input__clear) {
              color: #b3a8c9;
            }
          }

          .enter-hint {
            margin: 0 8px 0 4px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.5px;
            color: #8b6ab0;
            background: linear-gradient(
              120deg,
              rgba(255, 143, 184, 0.22),
              rgba(155, 123, 255, 0.22)
            );
            border-radius: 999px;
            user-select: none;
            white-space: nowrap;
          }
        }
      }

      .header-right {
        display: flex;
        gap: 10px;
        align-items: center;

        .user-info {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 5px 14px 5px 6px;
          border-radius: 999px;
          cursor: pointer;
          border: 1px solid transparent;
          transition: all 0.25s ease;

          &:hover {
            border-color: rgba(255, 143, 184, 0.45);
            background: rgba(255, 255, 255, 0.75);
            box-shadow: 0 6px 16px rgba(155, 123, 255, 0.16);
          }

          .user-avatar {
            // 渐变描边的头像圈，二次元站点常见的处理
            background: $gradient-brand;
            color: #fff;
            border: 2px solid rgba(255, 255, 255, 0.95);
            box-shadow: 0 0 0 1px rgba(155, 123, 255, 0.35);
          }

          .user-name {
            font-size: 0.92rem;
            color: $ink;
            font-weight: 600;
          }
        }
      }
    }
  }

  // ==================== 左侧侧边栏 ====================
  .layout-aside {
    position: relative;
    @include glass-panel(0.68);
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 0.9);
    min-height: calc(100vh - #{$header-h});
    overflow-y: auto;
    overflow-x: hidden;

    // 左上角一团柔光，避免整块面板太平
    &::before {
      content: '';
      position: absolute;
      top: -70px;
      left: -50px;
      width: 230px;
      height: 230px;
      background: radial-gradient(circle, rgba(255, 143, 184, 0.4), transparent 68%);
      pointer-events: none;
      z-index: 0;
    }

    .aside-content {
      position: relative;
      z-index: 1;
      padding: 12px 0;
      /* 纵向排布并让菜单占满剩余高度，知识库入口自然贴底 */
      display: flex;
      flex-direction: column;
      min-height: calc(100vh - #{$header-h});
      box-sizing: border-box;

      .aside-menu {
        /* 占满剩余空间，把知识库入口挤到底部 */
        flex: 1;

        .aside-menu-list {
          border-right: none;
          background: transparent;
          padding: 4px 0;

          .el-menu-item {
            position: relative;
            height: 46px;
            line-height: 46px;
            margin: 4px 12px;
            padding: 0 14px !important;
            border-radius: 12px;
            color: $ink-soft;
            font-size: 0.92rem;
            font-weight: 500;
            letter-spacing: 0.3px;
            transition: background 0.25s ease, color 0.25s ease, transform 0.25s ease,
              box-shadow 0.25s ease;

            .el-icon {
              font-size: 17px;
              margin-right: 10px;
              color: rgba(155, 123, 255, 0.9);
              transition: transform 0.25s ease;
            }

            &:hover {
              background: linear-gradient(
                90deg,
                rgba(255, 143, 184, 0.16),
                rgba(155, 123, 255, 0.1)
              );
              color: $violet-deep;
              transform: translateX(2px);

              .el-icon {
                transform: scale(1.14) rotate(-6deg);
              }
            }

            // 选中项：整块糖果渐变 + 微光
            &.is-active {
              background: $gradient-brand;
              color: #fff;
              font-weight: 700;
              box-shadow: 0 8px 20px rgba(155, 123, 255, 0.32);

              .el-icon {
                color: #fff;
              }

              // 右侧小光点，像被点亮
              &::after {
                content: '';
                position: absolute;
                right: 14px;
                top: 50%;
                width: 6px;
                height: 6px;
                margin-top: -3px;
                border-radius: 50%;
                background: #fff;
                box-shadow: 0 0 8px rgba(255, 255, 255, 0.95);
                opacity: 0.9;
              }
            }
          }
        }
      }

      /* ==================== 知识库入口（二次元风格） ==================== */
      .aside-knowledge {
        padding: 10px 12px 14px;
        margin-top: 8px;

        .kb-entry {
          position: relative;
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 11px 12px;
          border-radius: 14px;
          cursor: pointer;
          overflow: hidden;
          background: linear-gradient(120deg, #a78bfa 0%, #8b5cf6 48%, #ec4899 100%);
          box-shadow: 0 6px 16px rgba(139, 92, 246, 0.28);
          transition: transform 0.25s ease, box-shadow 0.25s ease;

          /* 星点纹理 */
          &::after {
            content: '';
            position: absolute;
            inset: 0;
            background-image: radial-gradient(rgba(255, 255, 255, 0.5) 1px, transparent 1px);
            background-size: 16px 16px;
            opacity: 0.45;
            pointer-events: none;
          }

          &:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 22px rgba(236, 72, 153, 0.35);

            .kb-entry-spark {
              transform: rotate(20deg) scale(1.15);
            }
          }

          &:active {
            transform: translateY(0);
          }

          .kb-entry-icon {
            position: relative;
            z-index: 1;
            flex-shrink: 0;
            font-size: 20px;
          }

          .kb-entry-text {
            position: relative;
            z-index: 1;
            flex: 1;
            min-width: 0;
            display: flex;
            flex-direction: column;
            line-height: 1.3;
          }

          .kb-entry-title {
            font-size: 0.88rem;
            font-weight: 700;
            color: #fff;
            letter-spacing: 0.5px;
          }

          .kb-entry-desc {
            font-size: 0.7rem;
            color: rgba(255, 255, 255, 0.85);
          }

          .kb-entry-spark {
            position: relative;
            z-index: 1;
            flex-shrink: 0;
            font-size: 14px;
            transition: transform 0.3s ease;
          }
        }
      }
    }
  }

  .layout-right-container {
    display: flex;
    flex-direction: column;
    height: calc(100vh - #{$header-h});

    .layout-main {
      flex: 1;
      padding: 0;
      overflow-y: auto;
      position: relative;

      .main-background {
        position: fixed;
        top: $header-h; /* Header 高度 */
        left: $aside-w; /* Aside 宽度 */
        right: 0;
        bottom: $footer-h; /* Footer 高度 */
        z-index: 0;

        .bg-image {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        // 覆盖层也带上一点粉紫，和整体主题统一
        .bg-overlay {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: linear-gradient(
            160deg,
            rgba(255, 255, 255, 0.64) 0%,
            rgba(255, 241, 248, 0.52) 44%,
            rgba(240, 246, 255, 0.58) 100%
          );
        }
      }

      .main-content {
        position: relative;
        z-index: 1;
        padding: 30px;
        min-height: calc(100vh - #{($header-h + $footer-h)});
      }
    }

    .layout-footer {
      position: relative;
      height: $footer-h;
      @include glass-panel(0.66);
      border: none;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;

      // 顶部渐变色发丝线，与 Header 呼应
      &::before {
        content: '';
        position: absolute;
        left: 0;
        right: 0;
        top: 0;
        height: 2px;
        background: linear-gradient(
          90deg,
          transparent 0%,
          rgba(120, 210, 255, 0.7) 22%,
          rgba(155, 123, 255, 0.75) 52%,
          rgba(255, 143, 184, 0.7) 78%,
          transparent 100%
        );
        opacity: 0.85;
        pointer-events: none;
      }

      // 中间一团极淡的粉色光晕，避免整条页脚是死板的横条
      &::after {
        content: '';
        position: absolute;
        left: 50%;
        bottom: -40px;
        width: 420px;
        height: 90px;
        transform: translateX(-50%);
        background: radial-gradient(ellipse, rgba(255, 143, 184, 0.22), transparent 70%);
        pointer-events: none;
      }

      .footer-inner {
        position: relative;
        z-index: 1;
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .footer-text {
        margin: 0;
        color: $ink-soft;
        font-size: 0.84rem;
        letter-spacing: 0.4px;
      }

      // 站名用品牌渐变字，和顶部 logo 呼应
      .footer-brand {
        font-weight: 700;
        background: $gradient-brand;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: 0.6px;
      }

      .footer-dot {
        margin: 0 6px;
        color: rgba(155, 123, 255, 0.5);
      }

      .footer-petal,
      .footer-spark {
        font-size: 0.82rem;
        line-height: 1;
        opacity: 0.85;
      }

      .footer-petal {
        animation: petal-sway 4.2s ease-in-out infinite;
      }

      .footer-spark {
        color: rgba(155, 123, 255, 0.75);
        animation: sparkle 2.8s ease-in-out infinite;
      }
    }
  }

  // 下拉菜单样式
  :deep(.el-dropdown-menu) {
    border-radius: 12px;
    box-shadow: 0 12px 30px rgba(123, 92, 240, 0.18);

    .el-dropdown-menu__item {
      display: flex;
      align-items: center;
      gap: 8px;
      border-radius: 8px;

      .el-icon {
        font-size: 1rem;
      }

      &:hover {
        background: linear-gradient(90deg, rgba(255, 143, 184, 0.14), rgba(155, 123, 255, 0.12));
        color: $violet-deep;
      }
    }
  }
}

// 渐变色动画
@keyframes gradient-shift {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

// 闪烁动画
@keyframes sparkle {
  0%,
  100% {
    opacity: 1;
    transform: scale(1) rotate(0deg);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.2) rotate(10deg);
  }
}

// 页脚花瓣轻轻摇摆
@keyframes petal-sway {
  0%,
  100% {
    transform: rotate(-8deg) translateY(0);
  }
  50% {
    transform: rotate(8deg) translateY(-3px);
  }
}
</style>
