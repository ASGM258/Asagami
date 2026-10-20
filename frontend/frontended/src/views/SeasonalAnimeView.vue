<template>
  <div class="seasonal-anime-view">
    <!-- 顶部轮播图 -->
    <div class="banner-section">
      <el-carousel 
        v-if="banners.length > 0"
        height="520px" 
        indicator-position="outside"
        :autoplay="true"
        :interval="5000"
        arrow="always"
      >
        <el-carousel-item v-for="banner in banners" :key="banner.mainId || banner.animeId">
          <div class="banner-card" @click="goToDetail(banner)">
            <!-- 渐变遮罩 -->
            <div class="banner-overlay"></div>
            
            <!-- 内容区域：左右布局 -->
            <div class="banner-content">
              <!-- 左侧图片 -->
              <div class="banner-image-wrapper">
                <img 
                  :src="banner.coverImage" 
                  :alt="banner.title" 
                  class="banner-image"
                  @error="handleBannerImageError"
                />
              </div>
              
              <!-- 右侧文字信息 -->
              <div class="banner-info">
                <h1 class="banner-title">{{ banner.title }}</h1>
                
                <div class="banner-meta">
                  <span class="meta-item status-tag" :class="banner.status === 1 ? 'completed' : 'ongoing'">
                    {{ banner.status === 1 ? '已完结' : '连载中' }}
                  </span>
                  <span class="meta-item rating">
                    <el-icon><Star /></el-icon>
                    <span>{{ (banner.rating || 0).toFixed(1) }}</span>
                  </span>
                  <span v-if="banner.views" class="meta-item views">
                    <el-icon><View /></el-icon>
                    <span>{{ formatViews(banner.views) }} Views</span>
                  </span>
                </div>
                
                <p class="banner-synopsis">{{ truncateText(banner.synopsis, 120) }}</p>
                
                <div v-if="banner.genres && banner.genres.length > 0" class="banner-genres">
                  <el-tag 
                    v-for="genre in banner.genres.slice(0, 5)" 
                    :key="genre"
                    size="small"
                    effect="dark"
                    type="info"
                  >
                    {{ genre }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>
        </el-carousel-item>
      </el-carousel>
      
      <!-- 加载状态 -->
      <el-skeleton v-else-if="bannerLoading" :rows="3" animated class="banner-loading" />
    </div>

    <!-- 当季新番列表 -->
    <div class="seasonal-section">
      <div class="section-header">
        <h2 class="section-title">新番就要追着看</h2>
        
        <!-- 星期标签 -->
        <div class="day-tabs">
          <div 
            v-for="(day, index) in weekDays" 
            :key="index"
            class="day-tab"
            :class="{ active: selectedDay === index }"
            @click="selectDay(index)"
          >
            {{ day }}
          </div>
        </div>
        
        <!-- 刷新按钮 -->
        <el-button 
          type="primary" 
          size="small" 
          round
          :loading="refreshing"
          @click="handleRefreshSeasonal"
          class="refresh-btn"
        >
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        
        <el-button type="danger" round size="small" class="more-btn">更多</el-button>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="2" animated />
      </div>

      <!-- 动漫列表 -->
      <div v-else-if="animeList.length > 0" class="anime-list">
        <div 
          v-for="anime in animeList" 
          :key="anime.mainId || anime.id" 
          class="anime-card"
          @click="goToDetail(anime)"
        >
          <!-- 封面图容器 -->
          <div class="cover-container">
            <!-- 加载占位符 -->
            <div v-if="!imageLoaded[anime.mainId || anime.id]" class="image-placeholder">
              <el-icon :size="40" color="#909399"><Picture /></el-icon>
            </div>
            
            <img 
              :src="anime.coverImage" 
              :alt="anime.title" 
              class="cover-image"
              :class="{ 'loaded': imageLoaded[anime.mainId || anime.id] }"
              loading="lazy"
              @load="handleImageLoad(anime.mainId || anime.id)"
              @error="handleImageError($event, anime.mainId || anime.id)"
            />
            
            <!-- 评分标签（右下角） -->
            <div class="rating-badge">
              <span>{{ (anime.rating || 0).toFixed(1) }}</span>
            </div>
            
            <!-- 播放按钮（悬停显示） -->
            <div class="play-overlay">
              <el-icon :size="48"><VideoPlay /></el-icon>
            </div>
          </div>

          <!-- 信息区域 -->
          <div class="info-container">
            <h3 class="anime-title">{{ anime.title }}</h3>
            <p class="anime-episodes">{{ anime.episodes }} 集</p>
            <p class="anime-update-time">{{ formatUpdateTime(anime.updateTime) }}</p>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <el-empty v-else description="暂无该天的更新动漫" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { getBanners, getSeasonalAnime, refreshSeasonalAnime } from '@/api/anime'
import type { BannerItem, SeasonalAnime } from '@/types'
import { ElMessage } from 'element-plus'
import { Star, View, VideoPlay, Picture, Refresh } from '@element-plus/icons-vue'

const router = useRouter()

// 星期几的中文名称（0-6为周一到周日，7为待定）
const weekDays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日', '待定']

// 当前选中的星期（0表示周一，6表示周日，7表示待定）
const selectedDay = ref<number>(new Date().getDay() === 0 ? 6 : new Date().getDay() - 1)

// 轮播图数据
const banners = ref<BannerItem[]>([])
const bannerLoading = ref(false)

// 当季新番列表
const animeList = ref<SeasonalAnime[]>([])
const loading = ref(false)

// 图片加载状态跟踪
const imageLoaded = reactive<Record<string | number, boolean>>({})

// 刷新状态
const refreshing = ref(false)

// 获取轮播图数据
const fetchBanners = async () => {
  try {
    bannerLoading.value = true
    const response = await getBanners()
    
    if (response.code === 200 && response.data) {
      banners.value = response.data
    } else {
      ElMessage.error(response.message || '获取轮播图失败')
    }
  } catch (error: any) {
    console.error('获取轮播图错误:', error)
  } finally {
    bannerLoading.value = false
  }
}

// 获取当季新番列表
const fetchSeasonalAnime = async (dayOfWeek?: number) => {
  try {
    loading.value = true
    // 清空图片加载状态
    Object.keys(imageLoaded).forEach(key => delete imageLoaded[key])
    
    // dayOfWeek参数：1-7对应周一到周日，8表示待定（dayOfWeek为null）
    const response = await getSeasonalAnime(dayOfWeek)
    
    if (response.code === 200 && response.data) {
      animeList.value = response.data
    } else {
      ElMessage.error(response.message || '获取当季新番失败')
    }
  } catch (error: any) {
    console.error('获取当季新番错误:', error)
  } finally {
    loading.value = false
  }
}

// 选择星期
const selectDay = (dayIndex: number) => {
  selectedDay.value = dayIndex
  // dayIndex: 0-6对应周一到周日，7对应待定
  // 传给后端：1-7对应周一到周日，8表示待定（null）
  const backendParam = dayIndex === 7 ? 8 : (dayIndex + 1)
  fetchSeasonalAnime(backendParam)
}

// 处理刷新当季新番
const handleRefreshSeasonal = async () => {
  try {
    refreshing.value = true
    
    const response = await refreshSeasonalAnime()
    
    if (response.code === 200) {
      ElMessage.success({
        message: response.data || '刷新成功',
        duration: 3000  // 成功提示保持3秒
      })
      // 刷新成功后重新获取当前选中的星期数据
      const backendParam = selectedDay.value === 7 ? 8 : (selectedDay.value + 1)
      await fetchSeasonalAnime(backendParam)
    } else {
      // 刷新失败，统一提示用户5分钟后刷新
      ElMessage.warning({
        message: '后端正在刷新数据，请5分钟后刷新新番页面',
        duration: 500000  // 显示5分钟
      })
    }
  } catch (error: any) {
    console.error('刷新当季新番错误:', error)
    // 网络异常或超时，统一提示用户5分钟后刷新
    ElMessage.warning({
      message: '后端正在刷新数据，请5分钟后刷新新番页面',
      duration: 500000  // 显示5分钟
    })
  } finally {
    refreshing.value = false
  }
}

// 跳转到详情页
const goToDetail = async (item: BannerItem | SeasonalAnime) => {
  // 获取 mainId
  const mainId = item.mainId
  
  // 如果没有 mainId，提示用户该动漫信息不存在
  if (!mainId) {
    ElMessage.warning('该动漫信息不存在')
    return
  }
  
 router.push(`/anime/${mainId}`)
   
}

// 处理轮播图图片加载错误
const handleBannerImageError = (event: Event) => {
  const img = event.target as HTMLImageElement
  img.style.display = 'none'
}

// 处理动漫封面图片加载成功
const handleImageLoad = (id: string | number) => {
  imageLoaded[id] = true
}

// 处理动漫封面图片加载错误
const handleImageError = (event: Event, id: string | number) => {
  const img = event.target as HTMLImageElement
  // 设置默认占位图或使用背景色
  img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmN2ZhIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxOCIgZmlsbD0iIzkwOTM5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuS4reWbvTwvdGV4dD48L3N2Zz4='
  imageLoaded[id] = true
}

// 截断文本
const truncateText = (text: string, maxLength: number): string => {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

// 格式化观看次数
const formatViews = (views: number): string => {
  if (views >= 10000) {
    return (views / 10000).toFixed(1) + 'w'
  }
  return views.toString()
}

// 格式化更新时间
const formatUpdateTime = (updateTime?: string): string => {
  if (!updateTime) return ''
  
  // 如果已经是格式化好的字符串，直接返回
  if (updateTime.includes(':')) {
    return updateTime
  }
  
  // 否则解析时间并格式化
  try {
    const date = new Date(updateTime)
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${hours}:${minutes}`
  } catch {
    return updateTime
  }
}

// 组件挂载时加载数据
onMounted(() => {
  fetchBanners()
  fetchSeasonalAnime(selectedDay.value + 1)
})
</script>

<style scoped lang="scss">
.seasonal-anime-view {
  min-height: 100%;
  background-color: #f5f7fa2a;

  // 轮播图区域
  .banner-section {
    margin-bottom: 40px;

    :deep(.el-carousel) {
      .el-carousel__container {
        border-radius: 8px;
        overflow: hidden;
      }

      .el-carousel__indicators--outside {
        bottom: 20px;
      }
    }

      .banner-card {
        position: relative;
        width: 100%;
        height: 100%;
        cursor: pointer;
        overflow: hidden;
      
        .banner-overlay {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(245, 243, 243, 0.1);
          z-index: 1;
        }
      
        .banner-content {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: space-between;
          height: 100%;
          padding: 0 60px;
          gap: 40px;
          z-index: 2;
      
          .banner-image-wrapper {
            flex-shrink: 0;
            height: 80%;
            max-width: 350px;
            display: flex;
            align-items: center;
            justify-content: center;
      
            .banner-image {
              max-height: 100%;
              max-width: 100%;
              object-fit: contain;
              border-radius: 8px;
              box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            }
          }
      
          .banner-info {
            flex: 1;
            color: #fff;
            text-align: left;
            background-color: rgba(244, 244, 244, 0);
            padding: 30px;
            border-radius: 8px;
            backdrop-filter: blur(5px);

            .banner-title {
              font-size: 2.5rem;
              font-weight: 700;
              margin: 0 0 15px 0;
              text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
            }

            .banner-meta {
              display: flex;
              align-items: center;
              gap: 20px;
              margin-bottom: 15px;

              .meta-item {
                display: flex;
                align-items: center;
                gap: 5px;
                font-size: 1rem;

                &.status-tag {
                  padding: 4px 12px;
                  border-radius: 4px;
                  font-size: 0.9rem;
                  font-weight: 500;

                  &.completed {
                    background-color: #67c23a;
                  }

                  &.ongoing {
                    background-color: #f56c6c;
                  }
                }

                &.rating {
                  color: #ffd700;
                  font-weight: 600;

                  .el-icon {
                    font-size: 1.1rem;
                  }
                }

                &.views {
                  color: #e0e0e0;
                }
              }
            }

            .banner-synopsis {
              font-size: 1rem;
              line-height: 1.6;
              margin: 0 0 15px 0;
              opacity: 0.9;
            }

            .banner-genres {
              display: flex;
              gap: 8px;
              flex-wrap: wrap;
            }
          }
        }
      }

    .banner-loading {
      height: 520px;
      border-radius: 8px;
      background-color: #fff;
    }
  }

  // 当季新番区域
  .seasonal-section {
    padding: 0 20px 40px;

    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 25px;
      gap: 20px;

      .section-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #303133;
        margin: 0;
        white-space: nowrap;
      }

      .day-tabs {
        display: flex;
        gap: 10px;
        flex: 1;
        justify-content: center;

        .day-tab {
          padding: 8px 20px;
          border-radius: 20px;
          cursor: pointer;
          transition: all 0.3s ease;
          font-size: 0.95rem;
          color: #606266;
          background-color: #fff;
          border: 1px solid #dcdfe6;

          &:hover {
            color: #f56c6c;
            border-color: #f56c6c;
          }

          &.active {
            background-color: #f56c6c;
            color: #fff;
            border-color: #f56c6c;
          }
        }
      }

      .more-btn {
        white-space: nowrap;
      }

      .refresh-btn {
        display: flex;
        align-items: center;
        gap: 5px;
        white-space: nowrap;
        margin-right: 10px;

        .el-icon {
          font-size: 1rem;
        }
      }
    }

    .loading-container {
      background-color: #fff;
      border-radius: 8px;
      padding: 20px;
    }

    // 动漫列表
    .anime-list {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 20px;

      .anime-card {
        background-color: #fff;
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
              transform: scale(1.05);
            }

            .play-overlay {
              opacity: 1;
            }
          }
        }

        .cover-container {
          position: relative;
          width: 100%;
          aspect-ratio: 3 / 4;
          overflow: hidden;
          background-color: #f5f7fa;

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

          .rating-badge {
            position: absolute;
            bottom: 8px;
            right: 8px;
            background-color: rgba(0, 0, 0, 0.6);
            color: #ff4757;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9rem;
            font-weight: 700;
            backdrop-filter: blur(4px);
          }

          .play-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.4);
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity 0.3s ease;

            .el-icon {
              color: #fff;
            }
          }
        }

        .info-container {
          padding: 12px;

          .anime-title {
            font-size: 0.95rem;
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

          .anime-update-time {
            font-size: 0.85rem;
            color: #909399;
            margin: 0;
          }
        }
      }
    }
  }
}

// 响应式布局
@media (max-width: 1600px) {
  .seasonal-anime-view {
    .seasonal-section {
      .anime-list {
        grid-template-columns: repeat(5, 1fr);
      }
    }
  }
}

@media (max-width: 1200px) {
  .seasonal-anime-view {
    .banner-section {
      .banner-card {
        .banner-content {
          .banner-title {
            font-size: 2rem;
          }

          .banner-synopsis {
            font-size: 0.9rem;
          }
        }
      }
    }

    .seasonal-section {
      .anime-list {
        grid-template-columns: repeat(4, 1fr);
      }

      .section-header {
        flex-direction: column;
        align-items: flex-start;

        .day-tabs {
          width: 100%;
          overflow-x: auto;
          padding-bottom: 10px;
        }
      }
    }
  }
}

@media (max-width: 768px) {
  .seasonal-anime-view {
    .banner-section {
      .banner-card {
        .banner-content {
          bottom: 40px;
          left: 30px;
          right: 30px;

          .banner-title {
            font-size: 1.5rem;
          }

          .banner-meta {
            flex-wrap: wrap;
            gap: 10px;
          }

          .banner-synopsis {
            display: none;
          }
        }
      }
    }

    .seasonal-section {
      .anime-list {
        grid-template-columns: repeat(2, 1fr);
      }
    }
  }
}

@media (max-width: 480px) {
  .seasonal-anime-view {
    .banner-section {
      .banner-card {
        .banner-content {
          .banner-title {
            font-size: 1.2rem;
          }
        }
      }
    }

    .seasonal-section {
      .anime-list {
        grid-template-columns: repeat(1, 1fr);
      }
    }
  }
}
</style>
