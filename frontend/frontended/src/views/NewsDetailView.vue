<template>
  <div class="news-detail-view">
    <!-- 顶部操作栏 -->
    <div class="detail-toolbar">
      <el-button link :icon="ArrowLeft" @click="goBack">返回资讯列表</el-button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 详情内容 -->
    <div v-else-if="newsDetail" class="detail-content">
      <article class="news-article">
        <!-- 标题与元信息 -->
        <header class="article-header">
          <div class="title-row">
            <span v-if="newsDetail.category" class="category-tag">{{ newsDetail.category }}</span>
            <h1 class="article-title">{{ newsDetail.title }}</h1>
          </div>

          <div class="article-meta">
            <span class="meta-item">{{ formatDateTime(newsDetail.publishTime) }}</span>
            <span class="meta-item">来源：{{ newsDetail.source || '未知' }}</span>
            <span class="meta-item">发布：{{ newsDetail.author || '匿名' }}</span>
            <span class="meta-item views">
              <el-icon><View /></el-icon>
              <span>{{ formatNumber(newsDetail.viewCount) }} 阅读</span>
            </span>
          </div>
        </header>

        <!-- 封面图 -->
        <div v-if="newsDetail.coverImage" class="article-cover">
          <img
            :src="newsDetail.coverImage"
            :alt="newsDetail.title"
            loading="lazy"
            @error="handleImageError"
          />
        </div>

        <!-- 正文 -->
        <section class="article-body" v-html="formatContent(newsDetail.content)"></section>

        <!-- 标签 -->
        <footer v-if="newsDetail.tags && newsDetail.tags.length > 0" class="article-footer">
          <div class="tag-list">
            <span v-for="tag in newsDetail.tags" :key="tag" class="tag-item">{{ tag }}</span>
          </div>
        </footer>

        <!-- 底部操作 -->
        <div class="article-actions">
          <el-button type="primary" plain :icon="Share" @click="handleShare">
            分享资讯
          </el-button>
          <el-button plain @click="goBack">返回列表</el-button>
        </div>
      </article>
    </div>

    <!-- 错误状态 -->
    <el-empty v-else description="资讯加载失败，请稍后重试">
      <el-button type="primary" @click="fetchNewsDetail">重新加载</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, View, Share } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getNewsDetail } from '@/api/news'
import type { NewsDetail, NewsDetailQueryRequest } from '@/types/news'
import { handleImageError } from '@/utils/image'
import { formatDateTime, formatNumber } from '@/utils/format'

const route = useRoute()
const router = useRouter()

// 资讯详情数据
const newsDetail = ref<NewsDetail | null>(null)
const loading = ref(false)

// 获取资讯详情
const fetchNewsDetail = async () => {
  try {
    loading.value = true
    const newsId = Number(route.params.id)

    if (!newsId) {
      ElMessage.error('无效的资讯ID')
      return
    }

    // 构建请求参数
    const request: NewsDetailQueryRequest = {
      newsId: newsId
    }

    const response = await getNewsDetail(request)

    if (response.code === 200 && response.data) {
      newsDetail.value = response.data
      // 同步修改浏览器标签标题
      document.title = `${response.data.title} - 动漫资讯`
    } else {
      ElMessage.error(response.message || '获取资讯详情失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '获取资讯详情失败')
    console.error('[NewsDetailView] 获取资讯详情异常:', error)
  } finally {
    loading.value = false
  }
}

// 将正文转换为可渲染的HTML
// 后端返回HTML时直接渲染，返回纯文本时按段落/换行转换
const formatContent = (content?: string): string => {
  if (!content) return '<p>暂无正文内容</p>'

  // 简单判断是否已经是HTML片段
  if (/<[a-z][\s\S]*>/i.test(content)) {
    return content
  }

  // 转义HTML特殊字符，避免纯文本中的尖括号被解析
  const escaped = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 空行分段，单换行转 <br>
  return escaped
    .split(/\n\s*\n/)
    .map(paragraph => `<p>${paragraph.replace(/\n/g, '<br>')}</p>`)
    .join('')
}

// 返回资讯列表
const goBack = () => {
  router.push('/news')
}

// 分享（复制当前资讯链接）
const handleShare = async () => {
  const shareUrl = window.location.href

  try {
    await navigator.clipboard.writeText(shareUrl)
    ElMessage.success('资讯链接已复制到剪贴板')
  } catch (error) {
    ElMessage.info(`请复制链接分享：${shareUrl}`)
  }
}

// 组件挂载时加载数据
onMounted(() => {
  fetchNewsDetail()
})
</script>

<style scoped lang="scss">
.news-detail-view {
  padding: 20px;
  min-height: 100%;

  .detail-toolbar {
    display: flex;
    align-items: center;
    margin-bottom: 16px;
  }

  .loading-container {
    background-color: rgba(255, 255, 255, 0.8);
    border-radius: 8px;
    padding: 20px;
  }

  .detail-content {
    .news-article {
      background-color: #fff;
      border-radius: 8px;
      padding: 30px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);

      .article-header {
        padding-bottom: 18px;
        border-bottom: 1px solid #ebeef5;

        .title-row {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          margin-bottom: 14px;

          .category-tag {
            flex-shrink: 0;
            margin-top: 6px;
            padding: 3px 10px;
            font-size: 0.8rem;
            color: #fff;
            background-color: #409eff;
            border-radius: 4px;
          }

          .article-title {
            margin: 0;
            font-size: 1.7rem;
            font-weight: 700;
            color: #1f2329;
            line-height: 1.4;
          }
        }

        .article-meta {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 18px;
          font-size: 0.85rem;
          color: #909399;

          .meta-item {
            display: flex;
            align-items: center;
            gap: 4px;
          }
        }
      }

      // 封面图
      .article-cover {
        margin: 24px 0;
        border-radius: 8px;
        overflow: hidden;
        background-color: #f5f7fa;

        img {
          display: block;
          width: 100%;
          max-height: 480px;
          object-fit: cover;
        }
      }

      // 正文（v-html 内容，需用 :deep 穿透 scoped 作用域）
      .article-body {
        margin-top: 24px;
        font-size: 1rem;
        color: #303133;
        line-height: 1.9;

        :deep(p) {
          margin: 0 0 18px 0;
        }

        :deep(img) {
          max-width: 100%;
          height: auto;
          border-radius: 6px;
        }

        :deep(h2),
        :deep(h3) {
          margin: 26px 0 12px 0;
          color: #1f2329;
        }

        :deep(blockquote) {
          margin: 18px 0;
          padding: 12px 16px;
          border-left: 4px solid #409eff;
          background-color: #f5f7fa;
          border-radius: 0 6px 6px 0;
          color: #606266;
        }

        :deep(a) {
          color: #409eff;
          text-decoration: none;

          &:hover {
            text-decoration: underline;
          }
        }

        :deep(ul),
        :deep(ol) {
          padding-left: 22px;
          margin: 0 0 18px 0;
        }
      }

      // 标签
      .article-footer {
        margin-top: 30px;
        padding-top: 18px;
        border-top: 1px solid #ebeef5;

        .tag-list {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;

          .tag-item {
            padding: 3px 10px;
            font-size: 0.8rem;
            color: #55585e;
            background-color: #f0f1f3;
            border-radius: 3px;
          }
        }
      }

      // 底部操作
      .article-actions {
        display: flex;
        justify-content: center;
        gap: 12px;
        margin-top: 30px;
      }
    }
  }
}

// 响应式布局
@media (max-width: 768px) {
  .news-detail-view {
    padding: 12px;

    .detail-content {
      .news-article {
        padding: 16px;

        .article-header {
          .title-row .article-title {
            font-size: 1.3rem;
          }

          .article-meta {
            gap: 12px;
          }
        }

        .article-body {
          font-size: 0.95rem;
        }
      }
    }
  }
}
</style>
