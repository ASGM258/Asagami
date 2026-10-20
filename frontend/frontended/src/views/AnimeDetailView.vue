<template>
  <div class="anime-detail-view">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 详情内容 -->
    <div v-else-if="animeDetail" class="detail-content">
      <!-- 第一部分：动漫介绍 -->
      <div class="anime-info-section">
        <!-- 封面和基本信息 -->
        <div class="info-header">
          <div class="cover-wrapper">
            <!-- 加载占位符 -->
            <div v-if="!imageLoaded" class="image-placeholder">
              <el-icon :size="60" color="#909399"><Picture /></el-icon>
            </div>
            
            <img 
              :src="animeDetail.animeInfo.coverImage" 
              :alt="animeDetail.animeInfo.title"
              class="cover-image"
              :class="{ 'loaded': imageLoaded }"
              loading="lazy"
              @load="handleImageLoad"
              @error="handleImageError"
            />
          </div>
          
          <div class="basic-info">
            <h1 class="anime-title">{{ animeDetail.animeInfo.title }}</h1>
            
            <!-- 标签 -->
            <div class="genres-tags">
              <el-tag 
                v-for="genre in animeDetail.animeInfo.genres" 
                :key="genre"
                size="small"
                effect="plain"
              >
                {{ genre }}
              </el-tag>
            </div>
            
            <!-- 详细信息 -->
            <div class="info-grid">
              <div class="info-item">
                <span class="label">评分：</span>
                <span class="value rating-value">
                  <el-rate 
                    v-model="animeDetail.animeInfo.rating" 
                    disabled 
                    show-score
                    text-color="#ff9900"
                  />
                </span>
              </div>
              
              <div class="info-item">
                <span class="label">集数：</span>
                <span class="value">{{ animeDetail.animeInfo.episodes }} 集</span>
              </div>
              
              <div class="info-item">
                <span class="label">状态：</span>
                <span class="value">
                  <el-tag :type="animeDetail.animeInfo.status === 1 ? 'success' : 'warning'" size="small">
                    {{ animeDetail.animeInfo.status === 1 ? '已完结' : '连载中' }}
                  </el-tag>
                </span>
              </div>
              
              <div class="info-item">
                <span class="label">发行时间：</span>
                <span class="value">{{ formatDate(animeDetail.animeInfo.releaseDate) }}</span>
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <div class="action-buttons">
              <el-button type="primary" size="large" @click="handleStartWatching">
                <el-icon><VideoPlay /></el-icon>
                开始观看
              </el-button>
              <el-dropdown trigger="click" @command="handleUpdateWatchStatus">
                <el-button size="large">
                  <el-icon><component :is="getWatchStatusIcon(currentWatchStatus)" /></el-icon>
                  {{ getWatchStatusLabel(currentWatchStatus) }}
                  <el-icon class="el-icon--right"><arrow-down /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item 
                      v-for="option in watchStatusOptions" 
                      :key="option.value"
                      :command="option.value"
                    >
                      <el-icon><component :is="option.icon" /></el-icon>
                      {{ option.label }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </div>
        
        <!-- 简介 -->
        <div class="synopsis-section">
          <h3 class="section-title">简介</h3>
          <p class="synopsis-text">{{ animeDetail.animeInfo.synopsis || '暂无简介' }}</p>
        </div>
      </div>

      <!-- 第二部分：评论区（参考B站样式） -->
      <div class="comments-section">
        <div class="comments-header">
          <h3 class="section-title">评论</h3>
          <span class="comments-count">共 {{ animeDetail.comments.length }} 条</span>
        </div>
        
        <!-- 发表评论 -->
        <div class="comment-input-wrapper">
          <el-avatar :size="40" class="user-avatar">
            <el-icon><User /></el-icon>
          </el-avatar>
          <div class="comment-input-box">
            <el-input
              v-model="newComment"
              type="textarea"
              :rows="3"
              placeholder="发一条友善的评论吧~"
              resize="none"
            />
            <div class="comment-actions">
              <span class="tip-text">文明发言，理性讨论</span>
              <el-button type="primary" @click="handleSubmitComment" :disabled="!newComment.trim()">
                发表评论
              </el-button>
            </div>
          </div>
        </div>
        
        <!-- 评论列表 -->
        <div class="comments-list">
          <div 
            v-for="comment in animeDetail.comments" 
            :key="comment.commentId"
            class="comment-item"
          >
            <!-- 评论人头像 -->
            <el-avatar :size="48" :src="comment.commenter.avatar" class="commenter-avatar">
              <el-icon><User /></el-icon>
            </el-avatar>
            
            <!-- 评论内容 -->
            <div class="comment-content">
              <!-- 评论人头信息 -->
              <div class="commenter-info">
                <span class="nickname">{{ comment.commenter.nickname }}</span>
                <span class="time">{{ formatTime(comment.createdAt) }}</span>
              </div>
              
              <!-- 评论文本或编辑框 -->
              <div v-if="editingCommentId === comment.commentId" class="edit-comment-box">
                <el-input
                  v-model="editingContent"
                  type="textarea"
                  :rows="2"
                  resize="none"
                />
                <div class="edit-actions">
                  <el-button size="small" @click="cancelEdit">取消</el-button>
                  <el-button size="small" type="primary" @click="saveEdit(comment.commentId)">保存</el-button>
                </div>
              </div>
              <div v-else class="comment-text">{{ comment.content }}</div>
              
              <!-- 评论操作栏 -->
              <div class="comment-actions-bar">
                <!-- 点赞按钮 -->
                <span 
                  class="action-item like-btn" 
                  :class="{ 'liked': comment.isLiked }"
                  @click="handleLikeComment(comment)"
                >
                  <el-icon><Check v-if="!comment.isLiked" /><Close v-else /></el-icon>
                  <span>{{ comment.likeCount || 0 }}</span>
                </span>
                <span class="action-item">
                  <el-icon><ChatDotRound /></el-icon>
                  <span>{{ comment.replyCount || 0 }} 回复</span>
                </span>
                <span class="action-item reply-btn" @click="startReply(comment.commentId)">回复</span>
                <!-- 如果是自己的评论，显示编辑和删除按钮 -->
                <template v-if="authStore.userInfo?.id === comment.commenter.userId">
                  <span class="action-item edit-btn" @click="startEditComment(comment as CommentResponse)">
                    <el-icon><Edit /></el-icon>
                    <span>编辑</span>
                  </span>
                  <span class="action-item delete-btn" @click="handleDeleteComment(comment.commentId)">
                    <el-icon><Delete /></el-icon>
                    <span>删除</span>
                  </span>
                </template>
              </div>
              
              <!-- 回复输入框 -->
              <div v-if="replyingToCommentId === comment.commentId" class="reply-input-box">
                <el-input
                  v-model="replyContent"
                  type="textarea"
                  :rows="2"
                  resize="none"
                  placeholder="写下你的回复..."
                />
                <div class="reply-actions">
                  <el-button size="small" @click="cancelReply">取消</el-button>
                  <el-button size="small" type="primary" @click="handleSubmitReply(comment.commentId)">发表回复</el-button>
                </div>
              </div>
              
              <!-- 回复列表 -->
              <div v-if="comment.replies && comment.replies.length > 0" class="replies-list">
                <div 
                  v-for="reply in comment.replies" 
                  :key="reply.replyId"
                  class="reply-item"
                >
                  <!-- 回复人头像 -->
                  <el-avatar :size="32" :src="reply.replier.avatar" class="replier-avatar">
                    <el-icon><User /></el-icon>
                  </el-avatar>
                  
                  <!-- 回复内容 -->
                  <div class="reply-content">
                    <!-- 回复人头信息 -->
                    <div class="replier-info">
                      <span class="nickname">{{ reply.replier.nickname }}</span>
                      <span class="time">{{ formatTime(reply.createdAt) }}</span>
                    </div>
                    
                    <!-- 回复文本 -->
                    <div class="reply-text">{{ reply.content }}</div>
                    
                    <!-- 回复操作栏 -->
                    <div class="reply-actions-bar">
                      <!-- 点赞按钮 -->
                      <span 
                        class="action-item like-btn" 
                        :class="{ 'liked': reply.isLiked }"
                        @click="handleLikeReply(reply)"
                      >
                        <el-icon><Check v-if="!reply.isLiked" /><Close v-else /></el-icon>
                        <span>{{ reply.likeCount || 0 }}</span>
                      </span>
                      <!-- 如果是自己的回复，显示删除按钮 -->
                      <template v-if="authStore.userInfo?.id === reply.replier.userId">
                        <span class="action-item delete-btn" @click="handleDeleteReply(reply.replyId)">
                          <el-icon><Delete /></el-icon>
                          <span>删除</span>
                        </span>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 空状态 -->
          <el-empty v-if="animeDetail.comments.length === 0" description="暂无评论，快来发表第一条评论吧！" />
        </div>
      </div>
    </div>

    <!-- 错误状态 -->
    <el-empty v-else description="加载失败，请稍后重试" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getAnimeDetail } from '@/api/anime'
import { updateWatchStatus } from '@/api/anime'
import { addComment, updateComment, deleteComment, getCommentList, addCommentReply, deleteCommentReply, likeTarget, getUserLikeStatus } from '@/api/comment'
import type { AnimeDetailResponse, AnimeDetailQueryRequest, CommentResponse, AddCommentRequest, UpdateCommentRequest, AddCommentReplyRequest } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoPlay, Star, User, ChatDotRound, Delete, Edit, Check, Close, Picture, ArrowDown } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const authStore = useAuthStore()

// 动漫详情数据
const animeDetail = ref<AnimeDetailResponse | null>(null)
const loading = ref(false)

// 图片加载状态
const imageLoaded = ref(false)

// 新评论内容
const newComment = ref('')

// 编辑中的评论
const editingCommentId = ref<number | null>(null)
const editingContent = ref('')

// 回复相关状态
const replyingToCommentId = ref<number | null>(null) // 正在回复的评论ID
const replyContent = ref('') // 回复内容

// 用户点赞状态
const likedCommentIds = ref<Set<number>>(new Set())
const likedReplyIds = ref<Set<number>>(new Set())

// 获取动漫详情
const fetchAnimeDetail = async () => {
  try {
    loading.value = true
    const animeId = Number(route.params.id)
    
    if (!animeId) {
      ElMessage.error('无效的动漫ID')
      return
    }
    
    // 构建请求参数
    const request: AnimeDetailQueryRequest = {
      animeId: animeId
    }
    
    const response = await getAnimeDetail(request)
    
    if (response.code === 200 && response.data) {
      animeDetail.value = response.data
      // 单独获取评论列表
      await fetchComments(animeId)
      // 从动漫详情中获取观看状态
      // 只有当用户已登录且有观看状态时才显示
      if (authStore.isLoggedIn && response.data.animeInfo.watchStatus !== undefined) {
        currentWatchStatus.value = response.data.animeInfo.watchStatus
        console.log('[AnimeDetailView] 加载观看状态:', currentWatchStatus.value)
      } else {
        // 未登录或无观看记录，保持undefined，显示"收藏"
        currentWatchStatus.value = undefined
      }
    } else {
      ElMessage.error(response.message || '获取动漫详情失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '获取动漫详情失败')
    console.error('获取动漫详情错误:', error)
  } finally {
    loading.value = false
  }
}

// 获取评论列表
const fetchComments = async (animeId: number) => {
  try {
    const response = await getCommentList(animeId)
    if (response.code === 200 && response.data) {
      console.log('[评论数据] 后端返回的原始数据:', JSON.stringify(response.data[0], null, 2))
      // 更新评论列表
      if (animeDetail.value) {
        animeDetail.value.comments = response.data
      }
    }
  } catch (error: any) {
    console.error('获取评论列表错误:', error)
    // 如果是401错误，说明需要登录
    if (error.message?.includes('登录') || error.message?.includes('401')) {
      ElMessage.warning('请先登录后查看评讻')
    }
  }
}

// 获取用户点赞状态
const fetchUserLikeStatus = async (animeId: number) => {
  if (!authStore.isLoggedIn) {
    return
  }
  
  try {
    const response = await getUserLikeStatus(animeId)
    if (response.code === 200 && response.data) {
      // 将数组转换为Set以便快速查找
      likedCommentIds.value = new Set(response.data.likedCommentIds || [])
      likedReplyIds.value = new Set(response.data.likedReplyIds || [])
      
      // 更新评论和回复的isLiked状态
      updateLikeStatusInComments()
    }
  } catch (error: any) {
    console.error('获取用户点赞状态错误:', error)
  }
}

// 更新评论和回复的点赞状态
const updateLikeStatusInComments = () => {
  if (!animeDetail.value) return
  
  console.log('[点赞状态] likedCommentIds:', Array.from(likedCommentIds.value))
  console.log('[点赞状态] likedReplyIds:', Array.from(likedReplyIds.value))
  
  // 遍历所有评论，设置isLiked状态
  animeDetail.value.comments.forEach(comment => {
    console.log(`[点赞状态] 处理评论ID: ${comment.commentId}, isLiked: ${likedCommentIds.value.has(comment.commentId)}`)
    comment.isLiked = likedCommentIds.value.has(comment.commentId)
    
    // 遍历回复，设置isLiked状态
    if (comment.replies) {
      comment.replies.forEach(reply => {
        reply.isLiked = likedReplyIds.value.has(reply.replyId)
      })
    }
  })
}

// 处理图片加载成功
const handleImageLoad = () => {
  imageLoaded.value = true
}

// 处理图片加载错误
const handleImageError = (event: Event) => {
  const img = event.target as HTMLImageElement
  // 设置默认占位图
  img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQwIiBoZWlnaHQ9IjMyMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmN2ZhIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxOCIgZmlsbD0iIzkwOTM5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuS4reWbvTwvdGV4dD48L3N2Zz4='
  imageLoaded.value = true
}

// 开始观看 - 跳转到次元城动漫首页
const handleStartWatching = () => {
  // 由于无法通过现有字段精确匹配次元城的动漫ID
  // 直接跳转到次元城首页，让用户自行搜索
  window.open('https://www.cycani.org/', '_blank')
}

// 当前观看状态
const currentWatchStatus = ref<number | undefined>(undefined)

// 观看状态选项
const watchStatusOptions = [
  { value: 0, label: '未开始', icon: 'VideoPause' },
  { value: 1, label: '观看中', icon: 'VideoPlay' },
  { value: 2, label: '已完成', icon: 'Check' },
  { value: 3, label: '已放弃', icon: 'Close' }
]

// 获取观看状态标签
const getWatchStatusLabel = (status?: number) => {
  if (status === undefined) return '收藏'
  const option = watchStatusOptions.find(opt => opt.value === status)
  return option ? option.label : '收藏'
}

// 获取观看状态图标
const getWatchStatusIcon = (status?: number) => {
  if (status === undefined) return Star
  const option = watchStatusOptions.find(opt => opt.value === status)
  return option ? option.icon : Star
}

// 更新观看状态
const handleUpdateWatchStatus = async (status: number) => {
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }
  
  try {
    const animeId = Number(route.params.id)
    console.log('[AnimeDetailView] 更新观看状态:', { animeId, status })
    
    const response = await updateWatchStatus({
      animeId: animeId,
      watchStatus: status
    })
    
    if (response.code === 200) {
      currentWatchStatus.value = status
      console.log('[AnimeDetailView] 状态更新成功，当前状态:', currentWatchStatus.value)
      ElMessage.success(`已设置为"${getWatchStatusLabel(status)}"`)
    } else {
      console.error('[AnimeDetailView] 状态更新失败:', response.message)
      ElMessage.error(response.message || '更新失败')
    }
  } catch (error: any) {
    console.error('[AnimeDetailView] 状态更新异常:', error)
    ElMessage.error(error.message || '更新失败')
  }
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

// 格式化时间
const formatTime = (timeStr: string) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  // 小于1分钟
  if (diff < 60000) {
    return '刚刚'
  }
  // 小于1小时
  if (diff < 3600000) {
    return `${Math.floor(diff / 60000)}分钟前`
  }
  // 小于1天
  if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)}小时前`
  }
  // 大于1天
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 提交评论
const handleSubmitComment = async () => {
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }
  
  if (!newComment.value.trim()) {
    ElMessage.warning('请输入评论内容')
    return
  }
  
  try {
    const animeId = Number(route.params.id)
    const request: AddCommentRequest = {
      animeId: animeId,
      content: newComment.value.trim()
    }
    
    const response = await addComment(request)
    
    if (response.code === 200) {
      ElMessage.success('评论发表成功')
      newComment.value = ''
      // 重新获取评论列表
      await fetchComments(animeId)
    } else {
      ElMessage.error(response.message || '发表评论失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '发表评论失败')
  }
}

// 开始编辑评论
const startEditComment = (comment: CommentResponse) => {
  editingCommentId.value = comment.commentId
  editingContent.value = comment.content
}

// 取消编辑
const cancelEdit = () => {
  editingCommentId.value = null
  editingContent.value = ''
}

// 保存编辑
const saveEdit = async (commentId: number) => {
  if (!editingContent.value.trim()) {
    ElMessage.warning('评论内容不能为空')
    return
  }
  
  try {
    const request: UpdateCommentRequest = {
      commentId: commentId,
      content: editingContent.value.trim()
    }
    
    const response = await updateComment(request)
    
    if (response.code === 200) {
      ElMessage.success('更新成功')
      editingCommentId.value = null
      editingContent.value = ''
      // 重新获取评论列表
      const animeId = Number(route.params.id)
      await fetchComments(animeId)
    } else {
      ElMessage.error(response.message || '更新失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '更新失败')
  }
}

// 删除评论
const handleDeleteComment = async (commentId: number) => {
  try {
    await ElMessageBox.confirm('确定要删除这条评论吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const response = await deleteComment(commentId)
    
    if (response.code === 200) {
      ElMessage.success('删除成功')
      // 重新获取评论列表
      const animeId = Number(route.params.id)
      await fetchComments(animeId)
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

// 点赞/取消点赞根评论
const handleLikeComment = async (comment: any) => {
  console.log('[点赞按钮点击] 接收到的comment对象:', JSON.stringify(comment, null, 2))
  
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }
  
  // 验证评论ID
  if (!comment || !comment.commentId) {
    console.error('评论对象或评论ID为空:', comment)
    ElMessage.error('无效的评论ID')
    return
  }
  
  try {
    // 切换点赞状态
    const type = comment.isLiked ? 'dislike' : 'like'
    console.log('[点赞] 完整comment对象:', comment)
    console.log('[点赞] comment.commentId:', comment.commentId, '类型:', typeof comment.commentId)
    console.log('[点赞] 操作:', type)
    
    if (!comment.commentId) {
      console.error('[点赞错误] commentId为空！')
      ElMessage.error('评论ID为空，无法点赞')
      return
    }
    
    const response = await likeTarget(comment.commentId, type, 'comment')
    
    if (response.code === 200) {
      // 更新本地状态
      if (comment.isLiked) {
        // 取消点赞
        likedCommentIds.value.delete(comment.commentId)
        comment.isLiked = false
        if (comment.likeCount && comment.likeCount > 0) {
          comment.likeCount--
        }
      } else {
        // 点赞
        likedCommentIds.value.add(comment.commentId)
        comment.isLiked = true
        comment.likeCount = (comment.likeCount || 0) + 1
      }
      ElMessage.success(type === 'like' ? '点赞成功' : '取消点赞')
    } else {
      ElMessage.error(response.message || '操作失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '操作失败')
  }
}

// 点赞/取消点赞回复
const handleLikeReply = async (reply: any) => {
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }
  
  try {
    // 切换点赞状态
    const type = reply.isLiked ? 'dislike' : 'like'
    const response = await likeTarget(reply.replyId, type, 'reply')
    
    if (response.code === 200) {
      // 更新本地状态
      if (reply.isLiked) {
        // 取消点赞
        likedReplyIds.value.delete(reply.replyId)
        reply.isLiked = false
        if (reply.likeCount && reply.likeCount > 0) {
          reply.likeCount--
        }
      } else {
        // 点赞
        likedReplyIds.value.add(reply.replyId)
        reply.isLiked = true
        reply.likeCount = (reply.likeCount || 0) + 1
      }
      ElMessage.success(type === 'like' ? '点赞成功' : '取消点赞')
    } else {
      ElMessage.error(response.message || '操作失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '操作失败')
  }
}

// 开始回复评论
const startReply = (commentId: number) => {
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }
  replyingToCommentId.value = commentId
  replyContent.value = ''
}

// 取消回复
const cancelReply = () => {
  replyingToCommentId.value = null
  replyContent.value = ''
}

// 提交回复
const handleSubmitReply = async (commentId: number) => {
  if (!replyContent.value.trim()) {
    ElMessage.warning('请输入回复内容')
    return
  }
  
  try {
    const request: AddCommentReplyRequest = {
      commentId: commentId,
      parentReplyId: null, // 直接回复主评论
      content: replyContent.value.trim()
    }
    
    const response = await addCommentReply(request)
    
    if (response.code === 200) {
      ElMessage.success('回复发表成功')
      replyContent.value = ''
      replyingToCommentId.value = null
      // 重新获取评论列表
      const animeId = Number(route.params.id)
      await fetchComments(animeId)
    } else {
      ElMessage.error(response.message || '发表回复失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '发表回复失败')
  }
}

// 删除回复
const handleDeleteReply = async (replyId: number) => {
  try {
    await ElMessageBox.confirm('确定要删除这条回复吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const response = await deleteCommentReply(replyId)
    
    if (response.code === 200) {
      ElMessage.success('删除成功')
      // 重新获取评论列表
      const animeId = Number(route.params.id)
      await fetchComments(animeId)
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

// 组件挂载时加载数据
onMounted(() => {
  fetchAnimeDetail()
})

// 监听路由参数变化，重新加载数据
watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId && newId !== oldId) {
      // 重置图片加载状态
      imageLoaded.value = false
      fetchAnimeDetail()
    }
  }
)

// 监听animeDetail变化，获取点赞状态
watch(
  () => animeDetail.value,
  (newValue) => {
    if (newValue && newValue.animeInfo?.id) {
      // 获取用户点赞状态
      fetchUserLikeStatus(newValue.animeInfo.id)
    }
  },
  { immediate: true }
)
</script>

<style scoped lang="scss">
.anime-detail-view {
  padding: 20px;
  min-height: 100%;
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 8px;

  .loading-container {
    padding: 20px;
  }

  .detail-content {
    max-width: 1200px;
    margin: 0 auto;
  }

  // ========== 动漫介绍部分 ==========
  .anime-info-section {
    margin-bottom: 40px;

    .info-header {
      display: flex;
      gap: 30px;
      margin-bottom: 30px;

      .cover-wrapper {
        flex-shrink: 0;
        width: 240px;
        position: relative;
        
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
          border-radius: 8px;
          z-index: 1;
        }
        
        .cover-image {
          width: 100%;
          aspect-ratio: 3 / 4;
          object-fit: cover;
          border-radius: 8px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
          transition: opacity 0.3s ease;
          opacity: 0;
          
          &.loaded {
            opacity: 1;
          }
        }
      }

      .basic-info {
        flex: 1;
        display: flex;
        flex-direction: column;

        .anime-title {
          font-size: 2rem;
          color: #303133;
          margin: 0 0 15px 0;
          font-weight: 700;
        }


        .info-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 15px;
          margin-bottom: 25px;

          .info-item {
            display: flex;
            align-items: center;
            font-size: 0.95rem;

            .label {
              color: #909399;
              margin-right: 8px;
            }

            .value {
              color: #303133;
              font-weight: 500;

              &.rating-value {
                display: flex;
                align-items: center;
              }
            }
          }
        }

        .action-buttons {
          display: flex;
          gap: 15px;
          margin-top: auto;

          .el-button {
            flex: 1;
            max-width: 200px;
          }
          
          // 观看状态下拉按钮样式
          .el-dropdown {
            flex: 1;
            max-width: 200px;
            
            .el-button {
              width: 100%;
            }
          }
        }
      }
    }

    .synopsis-section {
      background-color: #f5f7fa;
      padding: 20px;
      border-radius: 8px;

      .section-title {
        font-size: 1.3rem;
        color: #303133;
        margin: 0 0 15px 0;
        font-weight: 600;
      }

      .synopsis-text {
        color: #606266;
        line-height: 1.8;
        font-size: 0.95rem;
        margin: 0;
        white-space: pre-wrap;
      }
    }
  }

  // ========== 评论区部分（参考B站样式）==========
  .comments-section {
    border-top: 1px solid #e0e0e0;
    padding-top: 30px;

    .comments-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 25px;

      .section-title {
        font-size: 1.3rem;
        color: #303133;
        margin: 0;
        font-weight: 600;
      }

      .comments-count {
        color: #909399;
        font-size: 0.9rem;
      }
    }

    // 发表评论区域
    .comment-input-wrapper {
      display: flex;
      gap: 15px;
      margin-bottom: 30px;
      padding-bottom: 30px;
      border-bottom: 1px solid #e0e0e0;

      .user-avatar {
        flex-shrink: 0;
        background-color: #409eff;
        color: #fff;
      }

      .comment-input-box {
        flex: 1;

        .el-textarea {
          :deep(.el-textarea__inner) {
            border-radius: 8px;
            background-color: #f5f7fa;
            
            &:focus {
              background-color: #fff;
              border-color: #409eff;
            }
          }
        }

        .comment-actions {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-top: 10px;

          .tip-text {
            color: #909399;
            font-size: 0.85rem;
          }

          .el-button {
            min-width: 100px;
          }
        }
      }
    }

    // 评论列表
    .comments-list {
      .comment-item {
        display: flex;
        gap: 15px;
        padding: 20px 0;
        border-bottom: 1px solid #f0f0f0;

        &:last-child {
          border-bottom: none;
        }

        .commenter-avatar {
          flex-shrink: 0;
          background-color: #ecf5ff;
          color: #409eff;
        }

        .comment-content {
          flex: 1;

          .commenter-info {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;

            .nickname {
              color: #409eff;
              font-weight: 600;
              font-size: 0.95rem;
            }

            .time {
              color: #909399;
              font-size: 0.85rem;
            }
          }

          .comment-text {
            color: #303133;
            line-height: 1.6;
            font-size: 0.95rem;
            margin-bottom: 10px;
            word-break: break-word;
          }

          .edit-comment-box {
            margin-bottom: 10px;

            .el-textarea {
              :deep(.el-textarea__inner) {
                border-radius: 4px;
              }
            }

            .edit-actions {
              display: flex;
              gap: 10px;
              margin-top: 8px;
              justify-content: flex-end;
            }
          }

          .comment-actions-bar {
            display: flex;
            align-items: center;
            gap: 20px;
            font-size: 0.85rem;
            color: #909399;

            .action-item {
              display: flex;
              align-items: center;
              gap: 5px;
              cursor: pointer;
              transition: all 0.3s ease;
              padding: 4px 8px;
              border-radius: 4px;

              &:hover {
                background-color: #f0f2f5;
                color: #409eff;
              }

              .el-icon,
              svg {
                font-size: 1rem;
                width: 16px;
                height: 16px;
                transition: transform 0.2s ease;
              }
              
              // 点赞按钮样式（拇指）
              &.like-btn {
                position: relative;
                
                &:hover {
                  svg {
                    transform: scale(1.1);
                  }
                }
                
                &.liked {
                  color: #f56c6c;
                  font-weight: 500;
                  
                  svg {
                    fill: currentColor;
                    animation: likeAnimation 0.3s ease;
                  }
                }
              }

              &.reply-btn {
                margin-left: auto;
                
                &:hover {
                  color: #409eff;
                }
              }

              &.edit-btn,
              &.delete-btn {
                &:hover {
                  color: #f56c6c;
                }
              }
            }
          }
          
          // 回复输入框
          .reply-input-box {
            margin-top: 15px;
            padding: 15px;
            background-color: #f5f7fa;
            border-radius: 6px;
            
            .el-textarea {
              :deep(.el-textarea__inner) {
                border-radius: 4px;
              }
            }
            
            .reply-actions {
              display: flex;
              gap: 10px;
              margin-top: 10px;
              justify-content: flex-end;
            }
          }
          
          // 回复列表
          .replies-list {
            margin-top: 15px;
            padding-left: 20px;
            border-left: 2px solid #e0e0e0;
            
            .reply-item {
              display: flex;
              gap: 12px;
              padding: 12px 0;
              border-bottom: 1px solid #f0f0f0;
              
              &:last-child {
                border-bottom: none;
              }
              
              .replier-avatar {
                flex-shrink: 0;
              }
              
              .reply-content {
                flex: 1;
                min-width: 0;
                
                .replier-info {
                  display: flex;
                  align-items: center;
                  gap: 10px;
                  margin-bottom: 6px;
                  
                  .nickname {
                    font-weight: 600;
                    color: #303133;
                    font-size: 0.9rem;
                  }
                  
                  .time {
                    color: #909399;
                    font-size: 0.8rem;
                  }
                }
                
                .reply-text {
                  color: #606266;
                  line-height: 1.6;
                  font-size: 0.9rem;
                  margin-bottom: 8px;
                  word-break: break-word;
                }
                
                .reply-actions-bar {
                  display: flex;
                  align-items: center;
                  gap: 15px;
                  font-size: 0.8rem;
                  color: #909399;
                  
                  .action-item {
                    display: flex;
                    align-items: center;
                    gap: 4px;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    padding: 3px 6px;
                    border-radius: 3px;
                    
                    &:hover {
                      background-color: #f0f2f5;
                      color: #409eff;
                    }
                    
                    .el-icon,
                    svg {
                      font-size: 0.9rem;
                      width: 16px;
                      height: 16px;
                      transition: transform 0.2s ease;
                    }
                    
                    // 点赞按钮样式（拇指）
                    &.like-btn {
                      position: relative;
                      
                      &:hover {
                        svg {
                          transform: scale(1.1);
                        }
                      }
                      
                      &.liked {
                        color: #f56c6c;
                        font-weight: 500;
                        
                        svg {
                          fill: currentColor;
                          animation: likeAnimation 0.3s ease;
                        }
                      }
                    }
                    
                    &.delete-btn {
                      &:hover {
                        color: #f56c6c;
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}

// 响应式布局
@media (max-width: 768px) {
  .anime-detail-view {
    .anime-info-section {
      .info-header {
        flex-direction: column;
        align-items: center;
        text-align: center;

        .cover-wrapper {
          width: 200px;
        }

        .basic-info {
          .info-grid {
            grid-template-columns: 1fr;
          }

          .action-buttons {
            justify-content: center;
          }
        }
      }
    }

    .comments-section {
      .comment-input-wrapper {
        flex-direction: column;
        
        .user-avatar {
          align-self: flex-start;
        }
      }

      .comments-list {
        .comment-item {
          flex-direction: column;
          
          .commenter-avatar {
            align-self: flex-start;
          }
        }
      }
    }
  }
}

// 点赞动画
@keyframes likeAnimation {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.3);
  }
  100% {
    transform: scale(1);
  }
}
</style>
