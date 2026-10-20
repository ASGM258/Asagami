<template>
  <div class="news-list-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">动漫资讯</h1>
      <p class="page-description">最新动画、漫画、声优与活动动态，滚动到底部自动加载更多</p>
    </div>

    <!-- 筛选与操作区域 -->
    <div class="filter-section">
      <div class="filter-row">
        <span class="filter-label">分类</span>
        <div class="filter-options">
          <el-tag
            v-for="item in categories"
            :key="item.key"
            :type="currentCategory === item.key ? 'danger' : 'info'"
            :effect="currentCategory === item.key ? 'dark' : 'plain'"
            size="large"
            class="filter-tag"
            @click="handleCategoryChange(item.key)"
          >
            {{ item.name }}
          </el-tag>
        </div>

        <el-button
          type="primary"
          size="small"
          round
          :icon="Refresh"
          :loading="refreshing"
          class="refresh-btn"
          @click="handleRefresh"
        >
          {{ refreshing ? '抓取中…' : '刷新' }}
        </el-button>
      </div>
    </div>

    <!-- 资讯列表区域 -->
    <div ref="listRef" class="news-section">
      <div class="section-header">
        <h2 class="section-title">最新资讯</h2>
        <span class="total-count">共 {{ pagination.total }} 条</span>
      </div>

      <!-- 首屏加载骨架 -->
      <div v-if="loading && newsList.length === 0" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <!-- 资讯卡片列表 -->
      <div v-else-if="newsList.length > 0" class="news-list">
        <NewsCard
          v-for="item in newsList"
          :key="item.id"
          :news="item"
          @click="goToDetail"
        />
      </div>

      <!-- 空状态 -->
      <el-empty v-else description="暂无资讯数据" />

      <!-- 无限滚动哨兵：进入视口即加载下一页 -->
      <div ref="sentinelRef" class="scroll-sentinel">
        <!-- 加载中（上一批数据已展示） -->
        <div v-if="loadingStatus === 'loading'" class="loading-more">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在加载更多资讯...</span>
        </div>

        <!-- 加载失败，点击重试 -->
        <div v-else-if="loadingStatus === 'error'" class="loading-error" @click="loadNextPage">
          <span>加载失败，点击重试</span>
        </div>

        <!-- 已加载全部 -->
        <div v-else-if="loadingStatus === 'finished' && newsList.length > 0" class="loading-finished">
          <span>— 已经到底啦 —</span>
        </div>
      </div>
    </div>

    <!-- 回到顶部 -->
    <el-backtop :right="40" :bottom="60" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getNewsList, getNewsCategories, refreshNews, getRefreshStatus } from '@/api/news'
import type { NewsItem, NewsListQueryParams, NewsCategory } from '@/types/news'
import NewsCard from '@/components/NewsCard.vue'

const router = useRouter()

// 资讯列表数据
const newsList = ref<NewsItem[]>([])

// 加载状态：首屏加载 / 下一页加载中 / 是否已全部加载 / 加载失败
const loading = ref(false)
const loadingMore = ref(false)
const finished = ref(false)
const loadError = ref(false)

// 抓取中（服务端工作流执行期间为 true）
const refreshing = ref(false)
// 轮询定时器
let refreshTimer: number | undefined

// 当前分类（空字符串表示全部）
const currentCategory = ref<string>('')

// 资讯分类（接口失败时使用默认分类兜底）
const categories = ref<NewsCategory[]>([
  { key: '', name: '全部' },
  { key: '动画', name: '动画' },
  { key: '漫画', name: '漫画' },
  { key: '声优', name: '声优' },
  { key: '活动', name: '活动' }
])

// 分页信息（滚动加载只累加列表，页码内部递增）
const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

// 列表容器与滚动哨兵
const listRef = ref<HTMLElement | null>(null)
const sentinelRef = ref<HTMLElement | null>(null)

// 是否还有下一页
const hasMore = computed(() => !finished.value)

// 哨兵区状态：加载中 / 加载失败 / 已到底 / 可继续加载
const loadingStatus = computed<'loading' | 'error' | 'finished' | 'idle'>(() => {
  if (loadingMore.value) return 'loading'
  if (loadError.value) return 'error'
  if (finished.value) return 'finished'
  return 'idle'
})

// IntersectionObserver 实例与滚动容器
let observer: IntersectionObserver | null = null
let scrollContainer: HTMLElement | Window | null = null

// 查找页面真正的滚动容器（Layout 中 el-main / el-main 内层都可能滚动）
const findScrollContainer = (): HTMLElement | Window => {
  let parent = listRef.value?.parentElement || null

  while (parent) {
    const style = window.getComputedStyle(parent)
    const overflowY = style.overflowY
    const scrollable = overflowY === 'auto' || overflowY === 'scroll'

    if (scrollable && parent.scrollHeight > parent.clientHeight) {
      return parent
    }
    parent = parent.parentElement
  }

  return window
}

// 获取资讯分类（失败时保留默认分类，不阻塞列表）
const fetchCategories = async () => {
  try {
    const response = await getNewsCategories()

    if (response.code === 200 && response.data && response.data.length > 0) {
      // 保证「全部」始终在第一位
      const hasAll = response.data.some(item => item.key === '')
      categories.value = hasAll ? response.data : [{ key: '', name: '全部' }, ...response.data]
    }
  } catch (error) {
    console.log('[NewsListView] 分类接口暂不可用，使用默认分类')
  }
}

// 获取资讯列表（reset 为 true 表示重新从第一页开始）
const fetchNewsList = async (reset: boolean = false) => {
  // 正在请求时忽略重复触发
  if (loading.value || loadingMore.value) {
    return
  }

  if (reset) {
    pagination.pageNum = 1
    finished.value = false
    loadError.value = false
  }

  try {
    if (reset) {
      loading.value = true
    } else {
      loadingMore.value = true
    }

    // 构建查询参数
    const queryParams: NewsListQueryParams = {
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    }

    if (currentCategory.value) {
      queryParams.category = currentCategory.value
    }

    console.log('[NewsListView] 开始获取资讯列表, 参数:', JSON.stringify(queryParams))
    const response = await getNewsList(queryParams)

    if (response.code === 200 && response.data) {
      // 兼容 PageInfo 的 list 与 MyBatis-Plus 的 records 两种字段名
      const pageData = response.data as any
      const list: NewsItem[] = pageData.list || pageData.records || []

      newsList.value = reset ? list : [...newsList.value, ...list]
      pagination.total = pageData.total ?? newsList.value.length

      // 后端返回空列表或数量不足一页，视为已加载完毕
      if (list.length === 0 || list.length < pagination.pageSize) {
        finished.value = true
      } else if (pageData.pages && pagination.pageNum >= pageData.pages) {
        finished.value = true
      }

      loadError.value = false
    } else {
      ElMessage.error(response.message || '获取资讯列表失败')
      loadError.value = !reset
    }
  } catch (error: any) {
    console.error('[NewsListView] 获取资讯列表异常:', error)

    // 接口尚未就绪或网络异常时，给出友好提示并使用兜底数据展示
    if (reset && newsList.value.length === 0) {
      ElMessage.warning('资讯接口暂不可用，当前展示示例数据')
      newsList.value = getFallbackNewsList()
      pagination.total = newsList.value.length
      finished.value = true
    } else {
      loadError.value = true
      ElMessage.error(error.message || '获取资讯列表失败')
    }
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

// 加载下一页
const loadNextPage = async () => {
  if (loading.value || loadingMore.value || finished.value) {
    return
  }

  pagination.pageNum += 1
  await fetchNewsList()
}

// 切换分类
const handleCategoryChange = (key: string) => {
  if (currentCategory.value === key) return

  currentCategory.value = key
  newsList.value = []
  pagination.total = 0
  fetchNewsList(true)
}

/**
 * 手动刷新：先触发服务端抓取，再轮询状态，完成后重载列表
 *
 * 之前这个按钮只重新拉了一次列表，从来没有调用抓取接口，
 * 所以库里的数据永远是第一次抓下来的那批。
 */
const handleRefresh = async () => {
  if (refreshing.value) return

  refreshing.value = true
  try {
    // repair=true：顺带修复早期入库、正文只有 RSS 摘要（被截断）的条目
    const response = await refreshNews(undefined, true)

    if (response.code !== 200 || !response.data?.accepted) {
      ElMessage.warning(response.message || '抓取任务未能启动')
      refreshing.value = false
      return
    }

    ElMessage.info(response.data.message || '已开始抓取，正在后台执行')

    // 轮询：抓取 + 补全 + 多次模型调用，通常要几十秒
    const startedAt = Date.now()
    const MAX_WAIT_MS = 5 * 60 * 1000
    const POLL_INTERVAL_MS = 3000

    const poll = async () => {
      // 超时保护：避免服务端异常导致按钮永远转圈
      if (Date.now() - startedAt > MAX_WAIT_MS) {
        ElMessage.warning('抓取耗时较长，已停止等待，请稍后手动刷新列表')
        finishRefresh()
        return
      }

      try {
        const status = await getRefreshStatus()

        if (status.code === 200 && status.data && !status.data.running) {
          const last = status.data.lastRun
          if (last) {
            ElMessage.success(
              `抓取完成：新增/更新 ${last.published ?? 0} 条，拒绝 ${last.rejected ?? 0} 条`
            )
          } else {
            ElMessage.success('抓取完成')
          }
          finishRefresh()
          return
        }
      } catch (error) {
        // 单次轮询失败不终止，继续等
        console.warn('[NewsListView] 查询抓取状态失败:', error)
      }

      refreshTimer = window.setTimeout(poll, POLL_INTERVAL_MS)
    }

    const finishRefresh = () => {
      if (refreshTimer) {
        window.clearTimeout(refreshTimer)
        refreshTimer = undefined
      }
      refreshing.value = false
      // 重载列表（抓取完成后再拉，才能看到新数据和修复后的正文）
      newsList.value = []
      pagination.total = 0
      finished.value = false
      fetchNewsList(true)
      fetchCategories()
    }

    // 服务端可能已经跑完（很快失败的情况），先等一轮再判断
    refreshTimer = window.setTimeout(poll, POLL_INTERVAL_MS)
  } catch (error: any) {
    ElMessage.error(error.message || '触发抓取失败')
    refreshing.value = false
  }
}

// 跳转到资讯详情页
const goToDetail = (news: NewsItem) => {
  router.push(`/news/${news.id}`)
}

// 初始化无限滚动监听
const initObserver = () => {
  if (!sentinelRef.value || typeof IntersectionObserver === 'undefined') return

  scrollContainer = findScrollContainer()

  observer = new IntersectionObserver((entries) => {
    const entry = entries[0]

    // 哨兵进入视口且还有下一页时加载
    if (entry.isIntersecting && hasMore.value) {
      loadNextPage()
    }
  }, {
    root: scrollContainer === window ? null : (scrollContainer as HTMLElement),
    rootMargin: '200px 0px', // 提前 200px 预加载，滚动更顺滑
    threshold: 0
  })

  observer.observe(sentinelRef.value)
}

// 哨兵仍停留在视口内时（首屏不足一屏、切换分类、重试成功）继续加载下一页
watch(loadingStatus, (status) => {
  if (status !== 'idle' || !sentinelRef.value) return

  const rect = sentinelRef.value.getBoundingClientRect()
  const viewHeight = window.innerHeight || document.documentElement.clientHeight

  if (rect.top <= viewHeight + 200) {
    loadNextPage()
  }
})

// 组件挂载时加载数据
onMounted(() => {
  fetchCategories()
  fetchNewsList(true)
  initObserver()
})

// 组件卸载时断开监听并清掉抓取轮询
onUnmounted(() => {
  observer?.disconnect()
  observer = null
  if (refreshTimer) {
    window.clearTimeout(refreshTimer)
    refreshTimer = undefined
  }
})

// 接口不可用时的兜底示例数据（后端资讯接口上线后会自动被真实数据替换）
const getFallbackNewsList = (): NewsItem[] => {
  return [
    {
      id: 1,
      title: '《夜想曲～在这怪诞之夜～》预告影像公开',
      coverImage: '',
      summary: '原创动画电影《GROTESQQQUE -怪异-》其中一部作品《夜想曲～在这怪诞之夜～》公开最新预告影像。',
      category: '动画',
      source: '再漫画',
      author: '苦力A',
      publishTime: '2026-10-08 12:58',
      tags: ['预告影像', '原创动画电影']
    },
    {
      id: 2,
      title: '《雨夜之月》第一弹正式PV公开',
      coverImage: '',
      summary: '由くずしろ原作改编的TV动画《雨夜之月》，公开了主要配音阵容与第一弹正式PV。',
      category: '动画',
      source: '再漫画',
      author: '苦力A',
      publishTime: '2026-10-08 10:22',
      tags: ['PV', '配音阵容']
    },
    {
      id: 3,
      title: '恋爱喜剧《放学后归宅日常》动画化决定！',
      coverImage: '',
      summary: '松田舞创作的《放学后归宅日常》宣布TV动画化，将于2027年4月在日本电视台播出。',
      category: '动画',
      source: '再漫画',
      author: '苦力A',
      publishTime: '2026-10-07 21:13',
      tags: ['动画化', '恋爱', '喜剧']
    }
  ]
}
</script>

<style scoped lang="scss">
.news-list-view {
  padding: 20px;
  min-height: 100%;

  .page-header {
    margin-bottom: 30px;

    .page-title {
      font-size: 2rem;
      color: #303133;
      margin: 0 0 10px 0;
      font-weight: 600;
    }

    .page-description {
      font-size: 1.1rem;
      color: #606266;
      margin: 0;
    }
  }

  // 筛选区域
  .filter-section {
    background-color: rgba(255, 255, 255, 0);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 30px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);

    .filter-row {
      display: flex;
      align-items: center;
      gap: 15px;

      .filter-label {
        font-size: 0.95rem;
        color: #606266;
        font-weight: 500;
        min-width: 50px;
      }

      .filter-options {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        flex: 1;

        .filter-tag {
          cursor: pointer;
          transition: all 0.3s ease;
          user-select: none;

          &:hover {
            transform: translateY(-2px);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          }
        }
      }

      .refresh-btn {
        flex-shrink: 0;
      }
    }
  }

  .news-section {
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;

      .section-title {
        font-size: 1.5rem;
        color: #303133;
        margin: 0;
        font-weight: 600;
      }

      .total-count {
        font-size: 0.9rem;
        color: #909399;
      }
    }

    .loading-container {
      background-color: rgba(255, 255, 255, 0.8);
      border-radius: 8px;
      padding: 20px;
    }

    // 卡片纵向列表
    .news-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
      margin-bottom: 20px;
    }

    // 滚动哨兵
    .scroll-sentinel {
      min-height: 60px;
      display: flex;
      align-items: center;
      justify-content: center;

      .loading-more {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.9rem;
        color: #909399;

        .el-icon {
          font-size: 1.1rem;
        }
      }

      .loading-error {
        padding: 8px 16px;
        font-size: 0.9rem;
        color: #f56c6c;
        cursor: pointer;
        transition: all 0.3s ease;

        &:hover {
          text-decoration: underline;
        }
      }

      .loading-finished {
        font-size: 0.85rem;
        color: #c0c4cc;
        letter-spacing: 2px;
      }
    }
  }
}

// 响应式布局
@media (max-width: 768px) {
  .news-list-view {
    padding: 12px;

    .page-header {
      margin-bottom: 20px;

      .page-title {
        font-size: 1.5rem;
      }

      .page-description {
        font-size: 0.95rem;
      }
    }

    .filter-section {
      padding: 12px;
      margin-bottom: 20px;

      .filter-row {
        flex-wrap: wrap;
        gap: 10px;
      }
    }
  }
}
</style>
