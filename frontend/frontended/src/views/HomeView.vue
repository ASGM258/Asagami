<template>
  <div class="home-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">欢迎来到 浅上小站</h1>
      <p class="page-description">这里是你的动漫游戏管理中心</p>
    </div>

    <!-- 筛选区域 -->
    <div class="filter-section">
      <div class="filter-row">
        <span class="filter-label">年份</span>
        <div class="filter-options">
          <el-tag 
            v-for="year in yearOptions" 
            :key="year.value"
            :type="selectedYear === year.value ? 'danger' : 'info'"
            :effect="selectedYear === year.value ? 'dark' : 'plain'"
            size="large"
            @click="handleYearChange(year.value)"
            class="filter-tag"
          >
            {{ year.label }}
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 动漫列表区域 -->
    <div class="anime-section">
      <div class="section-header">
        <h2 class="section-title">动漫列表</h2>
        <span class="total-count">共 {{ pagination.total }} 部</span>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="4" animated />
      </div>

      <!-- 动漫网格 -->
      <div v-else-if="animeList.length > 0" class="anime-grid">
        <div 
          v-for="anime in animeList" 
          :key="anime.id" 
          class="anime-card"
          @click="goToDetail(anime.id)"
        >
          <!-- 封面图容器 -->
          <div class="cover-container">
            <!-- 加载占位符 -->
            <div v-if="!imageLoaded[anime.id]" class="image-placeholder">
              <el-icon :size="40" color="#909399"><Picture /></el-icon>
            </div>
            
            <img 
              :src="anime.coverImage" 
              :alt="anime.title" 
              class="cover-image"
              :class="{ 'loaded': imageLoaded[anime.id] }"
              loading="lazy"
              @load="handleImageLoad(anime.id)"
              @error="handleImageError($event, anime.id)"
            />
            <!-- 评分标签（右下角） -->
            <div class="rating-badge">
              <span>{{ (anime.rating || 0).toFixed(1) }}</span>
            </div>
            <!-- 观看状态图标（右上角） -->
            <el-dropdown trigger="click" @command="(status: number) => handleWatchStatusChange(anime, status)">
              <div class="watch-status-icon" :class="getWatchStatusClass(anime.watchStatus)" @click.stop>
                <svg viewBox="0 0 1024 1024" width="24" height="24">
                  <path d="M923 283.6c-13.4-31.1-32.6-58.9-56.9-82.8-45.3-44.5-106.5-69.1-174.8-69.1-89.6 0-169.2 52.1-207.9 127.9-38.7-75.8-118.3-127.9-207.9-127.9-68.3 0-129.5 24.6-174.8 69.1-24.3 23.9-43.5 51.7-56.9 82.8-33.9 78.9-21.1 171.2 34.1 236.9l388.9 388.9c12.5 12.5 32.8 12.5 45.3 0l388.9-388.9c55.1-65.7 68-158 34-236.9z"/>
                </svg>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :command="0">未开始</el-dropdown-item>
                  <el-dropdown-item :command="1">观看中</el-dropdown-item>
                  <el-dropdown-item :command="2">已完成</el-dropdown-item>
                  <el-dropdown-item :command="3">已放弃</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>

          <!-- 信息区域 -->
          <div class="info-container">
            <h3 class="anime-title">{{ anime.title }}</h3>
            <p class="anime-episodes">{{ anime.episodes }} 集</p>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <el-empty v-else description="暂无动漫数据" />

      <!-- 分页器 -->
      <div v-if="pagination.total > 0" class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.pageNum"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[16, 32, 48, 64]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import { getAnimeList, updateWatchStatus } from '@/api/anime'
import type { Anime, UpdateWatchStatusRequest, AnimeListQueryParams } from '@/types'
import { ElMessage } from 'element-plus'
import { Picture } from '@element-plus/icons-vue'

const router = useRouter()

// 动漫列表
const animeList = ref<Anime[]>([])
const loading = ref(false)

// 注入搜索查询
const searchQuery = inject<any>('searchQuery')

// 选中的年份（null表示全部）
const selectedYear = ref<number | null>(null)

// 图片加载状态跟踪
const imageLoaded = reactive<Record<number, boolean>>({})

// 生成年份选项（从当前年份往前推20年）
const currentYear = new Date().getFullYear()
const yearOptions: Array<{ value: number | null; label: string }> = Array.from({ length: 21 }, (_, i) => {
  const year = currentYear - i
  return {
    value: year,
    label: String(year)
  }
})
// 添加“全部”选项
yearOptions.unshift({ value: null, label: '全部' })

// 分页配置
const pagination = reactive({
  pageNum: 1,
  pageSize: 16,  // 一页16个（4x4）
  total: 0
})

// 获取动漫列表
const fetchAnimeList = async () => {
  try {
    loading.value = true
    console.log('[HomeView] 开始获取动漫列表...')
    
    // 清空图片加载状态
    for (const key in imageLoaded) {
      delete imageLoaded[key as unknown as number]
    }
    
    // 构建查询参数
    const queryParams: AnimeListQueryParams = {
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    }
    
    // 如果有搜索关键词，添加到查询参数中
    if (searchQuery?.value && searchQuery.value.trim()) {
      queryParams.title = searchQuery.value.trim()
    }
    
    // 如果选择了年份，添加到查询参数中
    if (selectedYear.value !== null) {
      queryParams.year = selectedYear.value
      console.log('[HomeView] 已选择年份:', selectedYear.value)
    } else {
      console.log('[HomeView] 未选择年份（查询全部）')
    }
    
    console.log('[HomeView] 最终请求参数:', JSON.stringify(queryParams, null, 2))
    
    const response = await getAnimeList(queryParams)
    console.log('[HomeView] API完整响应:', JSON.stringify(response, null, 2))
    console.log('[HomeView] response.code:', response.code)
    console.log('[HomeView] response.data:', response.data)

    if (response.code === 200 && response.data) {
      console.log('[HomeView] 数据加载成功, 总数:', response.data.total)
      console.log('[HomeView] 列表长度:', response.data.list?.length)
      animeList.value = response.data.list
      pagination.total = response.data.total
    } else {
      console.error('[HomeView] 数据加载失败:', response.message)
      console.error('[HomeView] 完整响应对象:', response)
      ElMessage.error(response.message || '获取动漫列表失败')
    }
  } catch (error: any) {
    console.error('[HomeView] 请求异常:', error)
    console.error('[HomeView] 错误详情:', {
      message: error.message,
      stack: error.stack
    })
    ElMessage.error(error.message || '获取动漫列表失败')
  } finally {
    loading.value = false
    console.log('[HomeView] 加载状态已关闭, animeList.length:', animeList.value.length)
  }
}

// 处理图片加载成功
const handleImageLoad = (id: number) => {
  imageLoaded[id] = true
}

// 处理图片加载错误
const handleImageError = (event: Event, id: number) => {
  const img = event.target as HTMLImageElement
  // 设置默认占位图
  img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmN2ZhIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxOCIgZmlsbD0iIzkwOTM5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuS4reWbvTwvdGV4dD48L3N2Zz4='
  imageLoaded[id] = true
}

// 跳转到动漫详情页
const goToDetail = (animeId: number) => {
  router.push(`/anime/${animeId}`)
}

// 页码改变
const handlePageChange = (page: number) => {
  pagination.pageNum = page
  fetchAnimeList()
  // 滚动到顶部
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// 每页数量改变
const handleSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.pageNum = 1
  fetchAnimeList()
}

// 处理搜索变化
const handleSearchChange = () => {
  pagination.pageNum = 1  // 重置到第一页
  fetchAnimeList()
}

// 处理年份选择
const handleYearChange = (year: number | null) => {
  console.log('[HomeView] 用户选择年份:', year === null ? '全部' : year)
  selectedYear.value = year
  pagination.pageNum = 1  // 重置到第一页
  fetchAnimeList()
}

// 根据观看状态获取对应的CSS类名
const getWatchStatusClass = (status?: number) => {
  if (!status || status === 0) return 'watch-status-empty'
  if (status === 1) return 'watch-status-watching'
  if (status === 2) return 'watch-status-completed'
  if (status === 3) return 'watch-status-dropped'
  return ''
}

// 处理观看状态变更
const handleWatchStatusChange = async (anime: Anime, status: number) => {
  try {
    // 构建请求数据，未赋值的字段传入 undefined（后端会处理为空）
    const requestData: UpdateWatchStatusRequest = {
      animeId: anime.id,
      watchStatus: status,
      currentEpisode: undefined,  // 当前集数（未赋值）
      rating: undefined,          // 评分（未赋值）
      comment: undefined,         // 评论（未赋值）
      tags: undefined             // 标签（未赋值）
    }
    
    const response = await updateWatchStatus(requestData)
    
    if (response.code === 200) {
      // 更新本地状态
      anime.watchStatus = status
      
      // 显示成功消息
      const statusTextMap: Record<number, string> = {
        0: '未开始',
        1: '观看中',
        2: '已完成',
        3: '已放弃'
      }
      ElMessage.success(`已将《${anime.title}》标记为${statusTextMap[status]}`)
    } else {
      ElMessage.error(response.message || '更新观看状态失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '更新观看状态失败')
  }
}

// 组件挂载时加载数据
onMounted(() => {
  console.log('[HomeView] 组件已挂载，开始加载数据...')
  fetchAnimeList()
  // 监听搜索变化事件
  window.addEventListener('searchChange', handleSearchChange)
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('searchChange', handleSearchChange)
})
</script>

<style scoped lang="scss">
.home-view {
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
    }
  }

  .anime-section {
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

    // 动漫网格布局
    .anime-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr); // 一行4个
      gap: 20px;
      margin-bottom: 30px;

      .anime-card {
        background-color: rgba(255, 255, 255, 0);
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
        cursor: pointer;

        &:hover {
          transform: translateY(-5px);
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);

          .cover-container {
            .cover-image {
              transform: scale(1.05); // 鼠标悬浮放大效果
            }
          }
        }

        // 封面图容器
        .cover-container {
          position: relative;
          width: 100%;
          aspect-ratio: 3 / 4; // 3:4 比例
          overflow: hidden;
          background-color: #f5f7fa; // 默认浅灰色背景

          .image-placeholder {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #f5f7fa;
            z-index: 1;
          }

          .cover-image {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s ease, opacity 0.3s ease;
            opacity: 0;

            &.loaded {
              opacity: 1;
            }
          }

          // 评分标签（右下角）- 参考右图样式
          .rating-badge {
            position: absolute;
            bottom: 8px;
            right: 8px;
            background-color: rgba(0, 0, 0, 0.6);
            color: #ff4757; // 红色文字
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9rem;
            font-weight: 700;
            backdrop-filter: blur(4px); // 毛玻璃效果
          }
        }

        // 观看状态图标（右上角）
        .watch-status-icon {
          position: absolute;
          top: 8px;
          right: 8px;
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.3s ease;
          z-index: 10; // 提高层级，确保可以点击
          cursor: pointer; // 显示手型光标

          svg {
            width: 100%;
            height: 100%;
            filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
            pointer-events: none; // 让点击事件穿透到父元素
          }

          // 空心爱心（未开始）
          &.watch-status-empty {
            svg path {
              fill: none;
              stroke: #fff;
              stroke-width: 40;
            }
          }

          // 绿色实心爱心（观看中）
          &.watch-status-watching {
            svg path {
              fill: #52c41a;
              stroke: none;
            }
          }

          // 红色实心爱心（已完成）
          &.watch-status-completed {
            svg path {
              fill: #ff4757;
              stroke: none;
            }
          }

          // 灰色实心爱心（已放弃）
          &.watch-status-dropped {
            svg path {
              fill: #bfbfbf;
              stroke: none;
            }
          }
        }

        // 信息区域
        .info-container {
          padding: 12px;

          .anime-title {
            font-size: 1rem;
            color: #303133;
            margin: 0 0 6px 0;
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }

          .anime-episodes {
            font-size: 0.85rem;
            color: #909399;
            margin: 0;
          }
        }
      }
    }

    // 分页器
    .pagination-container {
      display: flex;
      justify-content: center;
      padding: 20px 0;
      background-color: rgba(255, 255, 255, 0.8);
      border-radius: 8px;
    }
  }
}

// 响应式布局
@media (max-width: 1200px) {
  .home-view {
    .anime-section {
      .anime-grid {
        grid-template-columns: repeat(3, 1fr); // 平板：一行3个
      }
    }
  }
}

@media (max-width: 768px) {
  .home-view {
    .anime-section {
      .anime-grid {
        grid-template-columns: repeat(2, 1fr); // 小屏：一行2个
      }
    }
  }
}

@media (max-width: 480px) {
  .home-view {
    .anime-section {
      .anime-grid {
        grid-template-columns: repeat(1, 1fr); // 手机：一行1个
      }
    }
  }
}
</style>
