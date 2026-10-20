<template>
  <div class="character-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">动漫角色</h1>
      <p class="page-description">探索你喜爱的动漫角色</p>
    </div>

    <!-- 搜索区域 -->
    <div class="search-section">
      <el-input
        v-model="searchName"
        placeholder="搜索角色名称（支持中英文）"
        clearable
        size="large"
        @keyup.enter="handleSearch"
        @clear="handleClearSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
        <template #append>
          <el-button @click="handleSearch">搜索</el-button>
        </template>
      </el-input>
    </div>

    <!-- 角色列表区域 -->
    <div class="character-section">
      <div class="section-header">
        <h2 class="section-title">角色列表</h2>
        <span class="total-count">共 {{ pagination.total }} 个</span>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="4" animated />
      </div>

      <!-- 角色网格 -->
      <div v-else-if="characterList.length > 0" class="character-grid">
        <div 
          v-for="character in characterList" 
          :key="character.id" 
          class="character-card"
        >
          <!-- 头像容器 -->
          <div class="avatar-container" @click="goToDetail(character.id)">
            <!-- 加载占位符 -->
            <div v-if="!imageLoaded[character.id]" class="image-placeholder">
              <el-icon :size="50" color="#909399"><User /></el-icon>
            </div>
            
            <img 
              :src="character.imageUrl || getDefaultAvatar()" 
              :alt="character.name" 
              class="avatar-image"
              :class="{ 'loaded': imageLoaded[character.id] }"
              loading="lazy"
              @load="handleImageLoad(character.id)"
              @error="handleImageError($event, character.id)"
            />
            
            <!-- 喜欢按钮（右上角） -->
            <div class="like-button" :class="{ 'liked': (character.isLiked ?? 0) === 1 }" @click.stop="toggleLike(character)">
              <svg viewBox="0 0 1024 1024" width="24" height="24">
                <path d="M923 283.6c-13.4-31.1-32.6-58.9-56.9-82.8-45.3-44.5-106.5-69.1-174.8-69.1-89.6 0-169.2 52.1-207.9 127.9-38.7-75.8-118.3-127.9-207.9-127.9-68.3 0-129.5 24.6-174.8 69.1-24.3 23.9-43.5 51.7-56.9 82.8-33.9 78.9-21.1 171.2 34.1 236.9l388.9 388.9c12.5 12.5 32.8 12.5 45.3 0l388.9-388.9c55.1-65.7 68-158 34-236.9z"/>
              </svg>
            </div>
          </div>

          <!-- 信息区域 -->
          <div class="info-container">
            <h3 class="character-name">{{ character.name }}</h3>
            <p v-if="character.nameJp" class="character-name-jp">{{ character.nameJp }}</p>
            <div class="character-stats">
              <span class="favorites">
                <el-icon><Star /></el-icon>
                {{ formatNumber(character.favorites) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <el-empty v-else description="暂无角色数据" />

      <!-- 分页器 -->
      <div v-if="pagination.total > 0" class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.pageNum"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[12, 24, 36, 48]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
          background
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { getCharacterList, updateCharacterFavorite } from '@/api/anime'
import type { Character, CharacterListQueryParams, PageResponse } from '@/types'
import { ElMessage } from 'element-plus'
import { Search, User, Star } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// 角色列表数据
const characterList = ref<Character[]>([])
const loading = ref(false)

// 图片加载状态
const imageLoaded = ref<Record<number, boolean>>({})

// 搜索关键词
const searchName = ref('')

// 分页信息
const pagination = reactive({
  pageNum: 1,
  pageSize: 12,  // 与主页保持一致
  total: 0
})

// 获取默认头像
const getDefaultAvatar = () => {
  return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmN2ZhIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIyMCIgZmlsbD0iIzkwOTM5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuS4reWbvTwvdGV4dD48L3N2Zz4='
}

// 格式化数字（例如：15234 -> 1.5万）
const formatNumber = (num: number): string => {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  return num.toString()
}

// 获取角色列表
const fetchCharacterList = async () => {
  try {
    loading.value = true
    
    const params: CharacterListQueryParams = {
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    }
    
    // 如果有搜索关键词，添加到参数中
    if (searchName.value.trim()) {
      params.name = searchName.value.trim()
    }
    
    const response = await getCharacterList(params)
    
    if (response.code === 200 && response.data) {
      // 后端返回 PageInfo<CharacterSimpleDTO>,需要适配
      const pageInfo = response.data as any
      characterList.value = pageInfo.list || []
      pagination.total = pageInfo.total || 0
      pagination.pageNum = pageInfo.pageNum || 1
      pagination.pageSize = pageInfo.pageSize || 12
      
      // 重置图片加载状态
      imageLoaded.value = {}
      
      // 调试：打印分页信息和第一个角色的数据
      console.log('[角色列表] 分页信息:', {
        total: pageInfo.total,
        pageNum: pageInfo.pageNum,
        pageSize: pageInfo.pageSize,
        pages: pageInfo.pages,
        listLength: pageInfo.list?.length
      })
      if (characterList.value.length > 0) {
        console.log('[角色列表] 第一个角色数据:', characterList.value[0])
        console.log('[角色列表] isLiked值:', characterList.value[0].isLiked)
      }
    } else {
      ElMessage.error(response.message || '获取角色列表失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '获取角色列表失败')
    console.error('获取角色列表错误:', error)
  } finally {
    loading.value = false
  }
}

// 处理图片加载成功
const handleImageLoad = (characterId: number) => {
  imageLoaded.value[characterId] = true
}

// 处理图片加载错误
const handleImageError = (event: Event, characterId: number) => {
  const img = event.target as HTMLImageElement
  img.src = getDefaultAvatar()
  imageLoaded.value[characterId] = true
}

// 搜索
const handleSearch = () => {
  pagination.pageNum = 1
  fetchCharacterList()
}

// 清除搜索
const handleClearSearch = () => {
  searchName.value = ''
  pagination.pageNum = 1
  fetchCharacterList()
}

// 分页大小变化
const handleSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.pageNum = 1
  fetchCharacterList()
}

// 页码变化
const handlePageChange = (page: number) => {
  pagination.pageNum = page
  fetchCharacterList()
}

// 跳转到角色详情页
const goToDetail = (characterId: number) => {
  router.push(`/characters/${characterId}`)
}

// 切换喜欢状态
const toggleLike = async (character: Character) => {
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }
  
  try {
    const newStatus = character.isLiked === 1 ? 0 : 1
    
    const response = await updateCharacterFavorite({
      characterId: character.id,
      favoriteStatus: newStatus
    })
    
    if (response.code === 200) {
      // 更新本地状态
      character.isLiked = newStatus
      ElMessage.success(newStatus === 1 ? '喜欢成功' : '取消喜欢成功')
    } else {
      ElMessage.error(response.message || '操作失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '操作失败')
  }
}

// 组件挂载时加载数据
onMounted(() => {
  fetchCharacterList()
})
</script>

<style scoped lang="scss">
.character-view {
  padding: 20px;
  min-height: 100%;
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 8px;

  .page-header {
    text-align: center;
    margin-bottom: 30px;

    .page-title {
      font-size: 2rem;
      color: #303133;
      margin: 0 0 10px 0;
      font-weight: 700;
    }

    .page-description {
      font-size: 1rem;
      color: #909399;
      margin: 0;
    }
  }

  .search-section {
    max-width: 600px;
    margin: 0 auto 30px;
  }

  .character-section {
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
        color: #909399;
        font-size: 0.9rem;
      }
    }

    .loading-container {
      padding: 20px;
    }

    .character-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 20px;
      margin-bottom: 30px;

      .character-card {
        background-color: #fff;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
        cursor: pointer;

        &:hover {
          transform: translateY(-5px);
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
        }

        .avatar-container {
          position: relative;
          width: 100%;
          aspect-ratio: 1 / 1;
          background-color: #f5f7fa;
          cursor: pointer;
          
          .image-placeholder {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1;
          }
          
          .avatar-image {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: opacity 0.3s ease;
            opacity: 0;
            
            &.loaded {
              opacity: 1;
            }
          }
          
          // 喜欢按钮（右上角）
          .like-button {
            position: absolute;
            top: 8px;
            right: 8px;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background-color: rgba(255, 255, 255, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
            z-index: 2;
            
            svg {
              fill: none;
              stroke: #909399;
              stroke-width: 40;
              transition: all 0.3s ease;
            }
            
            &:hover {
              transform: scale(1.1);
              background-color: rgba(255, 255, 255, 1);
              
              svg {
                stroke: #f56c6c;
              }
            }
            
            &.liked {
              svg {
                fill: #f56c6c;
                stroke: #f56c6c;
              }
            }
          }
        }

        .info-container {
          padding: 12px;

          .character-name {
            font-size: 0.95rem;
            color: #303133;
            margin: 0 0 5px 0;
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }

          .character-name-jp {
            font-size: 0.8rem;
            color: #909399;
            margin: 0 0 8px 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }

          .character-stats {
            display: flex;
            align-items: center;
            gap: 5px;

            .favorites {
              display: flex;
              align-items: center;
              gap: 4px;
              font-size: 0.85rem;
              color: #f56c6c;
              font-weight: 500;

              .el-icon {
                font-size: 1rem;
              }
            }
          }
        }
      }
    }

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
@media (max-width: 768px) {
  .character-view {
    .character-section {
      .character-grid {
        grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: 15px;
      }
    }
  }
}
</style>
