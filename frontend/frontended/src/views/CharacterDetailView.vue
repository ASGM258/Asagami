<template>
  <div class="character-detail-view">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 详情内容 -->
    <div v-else-if="characterDetail" class="detail-content">
      <!-- 第一部分：角色介绍 -->
      <div class="character-info-section">
        <!-- 头像和基本信息 -->
        <div class="info-header">
          <div class="avatar-wrapper">
            <!-- 加载占位符 -->
            <div v-if="!imageLoaded" class="image-placeholder">
              <el-icon :size="60" color="#909399"><User /></el-icon>
            </div>
            
            <img 
              :src="characterDetail.characterInfo.imageUrl" 
              :alt="characterDetail.characterInfo.name"
              class="avatar-image"
              :class="{ 'loaded': imageLoaded }"
              loading="lazy"
              @load="handleImageLoad"
              @error="handleImageError"
            />
            
            <!-- 喜欢按钮（右上角） -->
            <div class="like-button" :class="{ 'liked': isLiked }" @click="toggleLike">
              <svg viewBox="0 0 1024 1024" width="28" height="28">
                <path d="M923 283.6c-13.4-31.1-32.6-58.9-56.9-82.8-45.3-44.5-106.5-69.1-174.8-69.1-89.6 0-169.2 52.1-207.9 127.9-38.7-75.8-118.3-127.9-207.9-127.9-68.3 0-129.5 24.6-174.8 69.1-24.3 23.9-43.5 51.7-56.9 82.8-33.9 78.9-21.1 171.2 34.1 236.9l388.9 388.9c12.5 12.5 32.8 12.5 45.3 0l388.9-388.9c55.1-65.7 68-158 34-236.9z"/>
              </svg>
            </div>
          </div>
          
          <div class="basic-info">
            <h1 class="character-name">{{ characterDetail.characterInfo.name }}</h1>
            <p v-if="characterDetail.characterInfo.nameJp" class="character-name-jp">{{ characterDetail.characterInfo.nameJp }}</p>
            
            <!-- 详细信息 -->
            <div class="info-grid">
              <div class="info-item">
                <span class="label">受欢迎程度：</span>
                <span class="value favorites-value">
                  <el-icon><Star /></el-icon>
                  {{ formatNumber(characterDetail.characterInfo.favorites) }}
                </span>
              </div>
              
              <div class="info-item">
                <span class="label">MAL ID：</span>
                <span class="value">{{ characterDetail.characterInfo.malId }}</span>
              </div>
              
              <div v-if="characterDetail.characterInfo.birthday" class="info-item">
                <span class="label">生日：</span>
                <span class="value">{{ characterDetail.characterInfo.birthday }}</span>
              </div>
              
              <div v-if="characterDetail.characterInfo.nicknames" class="info-item">
                <span class="label">别名：</span>
                <span class="value">{{ characterDetail.characterInfo.nicknames }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 简介 -->
        <div v-if="characterDetail.characterInfo.about" class="about-section">
          <h3 class="section-title">简介</h3>
          <p class="about-text">{{ characterDetail.characterInfo.about }}</p>
        </div>
      </div>

      <!-- 第二部分：评论区（参考动漫评论样式） -->
      <div class="comments-section">
        <div class="comments-header">
          <h3 class="section-title">评论</h3>
          <span class="comments-count">共 {{ characterDetail.comments.length }} 条</span>
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
            v-for="comment in characterDetail.comments" 
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
                  <span>{{ getReplyCount(comment) }} 回复</span>
                </span>
                <span class="action-item reply-btn" @click="startReply(comment.commentId)">回复</span>
                <!-- 如果是自己的评论，显示编辑和删除按钮 -->
                <template v-if="authStore.userInfo?.id === comment.commenter.userId">
                  <span class="action-item edit-btn" @click="startEditComment(comment)">
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
          <el-empty v-if="characterDetail.comments.length === 0" description="暂无评论，快来发表第一条评论吧！" />
        </div>
      </div>
    </div>

    <!-- 错误状态 -->
    <el-empty v-else description="加载失败，请稍后重试" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { 
  getCharacterDetail,
  updateCharacterFavorite, 
  addCharacterComment, 
  updateCharacterComment, 
  deleteCharacterComment, 
  getCharacterCommentList,
  getUserCharacterCommentLikeStatus,
  addCharacterCommentReply, 
  deleteCharacterCommentReply, 
  likeCharacterComment
} from '@/api/anime'
import type { CharacterDetailResponse, AddCharacterCommentReplyRequest } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Star, ChatDotRound, Delete, Edit, Check, Close } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const authStore = useAuthStore()

// 角色详情数据
const characterDetail = ref<CharacterDetailResponse | null>(null)
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

// 是否喜欢该角色
const isLiked = computed(() => characterDetail.value?.isLiked || false)

// 格式化数字（例如：15234 -> 1.5万）
const formatNumber = (num: number): string => {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  return num.toString()
}

// 获取回复数量
const getReplyCount = (comment: any): number => {
  if (!comment.replies) return 0
  let count = comment.replies.length
  comment.replies.forEach((reply: any) => {
    if (reply.childReplies) {
      count += reply.childReplies.length
    }
  })
  return count
}

// 获取角色详情
const fetchCharacterDetail = async () => {
  try {
    loading.value = true
    const characterId = Number(route.params.id)
    
    if (!characterId) {
      ElMessage.error('无效的角色ID')
      return
    }
    
    // 调用API获取角色详情
    const response = await getCharacterDetail(characterId)
    
    if (response.code === 200 && response.data) {
      characterDetail.value = response.data
      console.log('[CharacterDetailView] 加载角色详情, isLiked:', characterDetail.value.isLiked)
      // 单独获取评论列表（如果需要刷新）
      // await fetchComments(characterId)
    } else {
      ElMessage.error(response.message || '获取角色详情失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '获取角色详情失败')
    console.error('获取角色详情错误:', error)
  } finally {
    loading.value = false
  }
}

// 获取用户点赞状态（不再需要，因为isLiked已经从详情接口返回）
// const fetchUserLikeStatus = async (characterId: number) => {
//   // 不需要单独获取，isLiked已经在getCharacterDetail中返回
// }

// 局部刷新评论列表和用户点赞状态
const refreshCommentsAndLikeStatus = async (characterId: number) => {
  try {
    // 1. 获取最新的评论列表
    const commentsResponse = await getCharacterCommentList(characterId)
    if (commentsResponse.code === 200 && commentsResponse.data) {
      // 更新评论列表
      if (characterDetail.value) {
        characterDetail.value.comments = commentsResponse.data
      }
    }
    
    // 2. 获取用户对所有评论和回复的点赞状态
    const likeStatusResponse = await getUserCharacterCommentLikeStatus(characterId)
    if (likeStatusResponse.code === 200 && likeStatusResponse.data) {
      const { likedCommentIds, likedReplyIds } = likeStatusResponse.data
      
      // 更新评论的点赞状态
      if (characterDetail.value && characterDetail.value.comments) {
        characterDetail.value.comments.forEach(comment => {
          comment.isLiked = likedCommentIds.includes(comment.commentId)
          
          // 更新回复的点赞状态
          if (comment.replies) {
            comment.replies.forEach(reply => {
              reply.isLiked = likedReplyIds.includes(reply.replyId)
            })
          }
        })
      }
    }
  } catch (error: any) {
    console.error('刷新评论和点赞状态失败:', error)
  }
}

// 更新评论和回复的点赞状态
// const updateLikeStatusInComments = () => {
//   if (!characterDetail.value) return
// }

// 处理图片加载成功
const handleImageLoad = () => {
  imageLoaded.value = true
}

// 处理图片加载错误
const handleImageError = (event: Event) => {
  const img = event.target as HTMLImageElement
  // 设置默认占位图
  img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmN2ZhIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIyMCIgZmlsbD0iIzkwOTM5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuS4reWbvTwvdGV4dD48L3N2Zz4='
  imageLoaded.value = true
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

// 切换喜欢状态
const toggleLike = async () => {
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }
  
  try {
    const characterId = Number(route.params.id)
    const newStatus = isLiked.value ? 0 : 1
    console.log('[CharacterDetailView] 切换喜欢状态:', { characterId, currentIsLiked: isLiked.value, newStatus })
    
    const response = await updateCharacterFavorite({
      characterId: characterId,
      favoriteStatus: newStatus
    })
    
    if (response.code === 200) {
      // 更新本地状态
      if (characterDetail.value) {
        characterDetail.value.isLiked = !isLiked.value
        console.log('[CharacterDetailView] 状态更新成功, 新状态:', characterDetail.value.isLiked)
      }
      ElMessage.success(newStatus === 1 ? '喜欢成功' : '取消喜欢成功')
    } else {
      console.error('[CharacterDetailView] 状态更新失败:', response.message)
      ElMessage.error(response.message || '操作失败')
    }
  } catch (error: any) {
    console.error('[CharacterDetailView] 状态更新异常:', error)
    ElMessage.error(error.message || '操作失败')
  }
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
    const characterId = Number(route.params.id)
    const response = await addCharacterComment(characterId, newComment.value.trim())
    
    if (response.code === 200) {
      ElMessage.success('评论发表成功')
      newComment.value = ''
      // 局部刷新评论列表和用户点赞状态
      await refreshCommentsAndLikeStatus(characterId)
    } else {
      ElMessage.error(response.message || '发表评论失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '发表评论失败')
  }
}

// 开始编辑评论
const startEditComment = (comment: any) => {
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
    const response = await updateCharacterComment(commentId, editingContent.value.trim())
    
    if (response.code === 200) {
      ElMessage.success('更新成功')
      editingCommentId.value = null
      editingContent.value = ''
      // 局部刷新评论列表和用户点赞状态
      const characterId = Number(route.params.id)
      await refreshCommentsAndLikeStatus(characterId)
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
    
    const response = await deleteCharacterComment(commentId)
    
    if (response.code === 200) {
      ElMessage.success('删除成功')
      // 局部刷新评论列表和用户点赞状态
      const characterId = Number(route.params.id)
      await refreshCommentsAndLikeStatus(characterId)
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
    
    const response = await likeCharacterComment({
      targetType: 'comment',
      targetId: comment.commentId,
      type: type
    })
    
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
    
    const response = await likeCharacterComment({
      targetType: 'reply',
      targetId: reply.replyId,
      type: type
    })
    
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
    const request: AddCharacterCommentReplyRequest = {
      commentId: commentId,
      parentReplyId: null, // 直接回复主评论
      content: replyContent.value.trim()
    }
    
    const response = await addCharacterCommentReply(request)
    
    if (response.code === 200) {
      ElMessage.success('回复发表成功')
      replyContent.value = ''
      replyingToCommentId.value = null
      // 局部刷新评论列表和用户点赞状态
      const characterId = Number(route.params.id)
      await refreshCommentsAndLikeStatus(characterId)
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
    
    const response = await deleteCharacterCommentReply(replyId)
    
    if (response.code === 200) {
      ElMessage.success('删除成功')
      // 局部刷新评论列表和用户点赞状态
      const characterId = Number(route.params.id)
      await refreshCommentsAndLikeStatus(characterId)
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
  fetchCharacterDetail()
})

// 监听路由参数变化，重新加载数据
watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId && newId !== oldId) {
      // 重置图片加载状态
      imageLoaded.value = false
      fetchCharacterDetail()
    }
  }
)

// 监听characterDetail变化，获取点赞状态（已移除，因为isLiked直接从详情接口返回）
// watch(
//   () => characterDetail.value,
//   (newValue) => {
//     if (newValue && newValue.characterInfo?.id) {
//       // 获取用户点赞状态
//       fetchUserLikeStatus(newValue.characterInfo.id)
//     }
//   },
//   { immediate: true }
// )
</script>

<style scoped lang="scss">
.character-detail-view {
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

  // ========== 角色介绍部分 ==========
  .character-info-section {
    margin-bottom: 40px;

    .info-header {
      display: flex;
      gap: 30px;
      margin-bottom: 30px;

      .avatar-wrapper {
        flex-shrink: 0;
        width: 200px;
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
        
        .avatar-image {
          width: 100%;
          aspect-ratio: 1 / 1;
          object-fit: cover;
          border-radius: 8px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
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
          width: 40px;
          height: 40px;
          background-color: rgba(255, 255, 255, 0.9);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
          transition: all 0.3s ease;
          z-index: 10;
          
          svg {
            fill: #c0c4cc;
            transition: all 0.3s ease;
          }
          
          &:hover {
            transform: scale(1.1);
            background-color: rgba(255, 255, 255, 1);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            
            svg {
              fill: #f56c6c;
            }
          }
          
          &.liked {
            background-color: rgba(255, 255, 255, 0.9);
            
            svg {
              fill: #f56c6c;
            }
            
            &:hover {
              background-color: rgba(255, 255, 255, 1);
              
              svg {
                fill: #ff4d4f;
              }
            }
          }
        }
      }

      .basic-info {
        flex: 1;
        display: flex;
        flex-direction: column;

        .character-name {
          font-size: 2rem;
          color: #303133;
          margin: 0 0 10px 0;
          font-weight: 700;
        }

        .character-name-jp {
          font-size: 1.2rem;
          color: #909399;
          margin: 0 0 20px 0;
          font-style: italic;
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

              &.favorites-value {
                display: flex;
                align-items: center;
                gap: 5px;
                color: #f56c6c;

                .el-icon {
                  font-size: 1.1rem;
                }
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
            
            &.liked {
              background-color: #f56c6c;
              border-color: #f56c6c;
              color: #fff;
              
              &:hover {
                background-color: #f78989;
                border-color: #f78989;
              }
            }
          }
        }
      }
    }

    .about-section {
      background-color: #f5f7fa;
      padding: 20px;
      border-radius: 8px;

      .section-title {
        font-size: 1.3rem;
        color: #303133;
        margin: 0 0 15px 0;
        font-weight: 600;
      }

      .about-text {
        color: #606266;
        line-height: 1.8;
        font-size: 0.95rem;
        margin: 0;
        white-space: pre-wrap;
      }
    }
  }

  // ========== 评论区部分 ==========
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
              
              // 点赞按钮样式
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
                    
                    // 点赞按钮样式
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
  .character-detail-view {
    .character-info-section {
      .info-header {
        flex-direction: column;
        align-items: center;
        text-align: center;

        .avatar-wrapper {
          width: 180px;
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
