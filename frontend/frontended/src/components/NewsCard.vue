<template>
  <div class="news-card" @click="handleClick">
    <!-- 左侧缩略图 -->
    <div class="news-thumb">
      <!-- 加载占位符 -->
      <div v-if="!imageLoaded" class="image-placeholder">
        <el-icon :size="32" color="#c0c4cc"><Picture /></el-icon>
      </div>

      <img
        :src="news.coverImage || defaultImage"
        :alt="news.title"
        class="thumb-image"
        :class="{ 'loaded': imageLoaded }"
        loading="lazy"
        @load="handleImageLoad"
        @error="handleImageErrorInternal"
      />

      <!-- 分类角标（仅无分类文字时显示在图上，保证图片区域有信息） -->
      <div v-if="!news.category" class="thumb-category">资讯</div>
    </div>

    <!-- 右侧文字信息 -->
    <div class="news-body">
      <!-- 标题行：分类标签 + 标题 -->
      <div class="news-title-row">
        <span v-if="news.category" class="category-tag">{{ news.category }}</span>
        <h3 class="news-title" :title="news.title">{{ news.title }}</h3>
      </div>

      <!-- 元信息：时间 / 来源 / 发布 -->
      <div class="news-meta">
        <span class="meta-item publish-time">{{ formatDateTime(news.publishTime) }}</span>
        <span class="meta-item">来源：{{ news.source || '未知' }}</span>
        <span class="meta-item">发布：{{ news.author || '匿名' }}</span>
      </div>

      <!-- 摘要 -->
      <p class="news-summary">{{ news.summary || '暂无摘要' }}</p>

      <!-- 底部：标签 + 分享 -->
      <div class="news-footer">
        <div class="tag-list">
          <span v-for="tag in visibleTags" :key="tag" class="tag-item">{{ tag }}</span>
        </div>
        <span class="share-btn" @click.stop="handleShare">
          <el-icon><Share /></el-icon>
          <span>分享</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Picture, Share } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { handleImageError as applyImageError, getDefaultImage } from '@/utils/image'
import { formatDateTime } from '@/utils/format'
import type { NewsItem } from '@/types/news'

const props = withDefaults(defineProps<{
  news: NewsItem   // 资讯数据
  maxTags?: number // 最多展示的标签数量
}>(), {
  maxTags: 3
})

const emit = defineEmits<{
  (e: 'click', news: NewsItem): void
}>()

// 图片加载状态
const imageLoaded = ref(false)

// 默认占位图
const defaultImage = getDefaultImage()

// 最多展示 maxTags 个标签
const visibleTags = computed<string[]>(() => {
  const tags = props.news.tags || []
  return tags.slice(0, props.maxTags)
})

// 图片加载成功
const handleImageLoad = () => {
  imageLoaded.value = true
}

// 图片加载失败（先替换占位图，再结束加载态）
const handleImageErrorInternal = (event: Event) => {
  applyImageError(event)
  imageLoaded.value = true
}

// 点击卡片
const handleClick = () => {
  emit('click', props.news)
}

// 分享（复制当前资讯链接，浏览器不支持剪贴板时降级提示）
const handleShare = async () => {
  const shareUrl = `${window.location.origin}/news/${props.news.id}`

  try {
    await navigator.clipboard.writeText(shareUrl)
    ElMessage.success('资讯链接已复制到剪贴板')
  } catch (error) {
    ElMessage.info(`请复制链接分享：${shareUrl}`)
  }
}
</script>

<style scoped lang="scss">
.news-card {
  display: flex;
  gap: 18px;
  padding: 18px 20px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-3px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);

    .news-title {
      color: #409eff;
    }

    .thumb-image {
      transform: scale(1.05);
    }
  }

  // 左侧缩略图
  .news-thumb {
    position: relative;
    flex-shrink: 0;
    width: 200px;
    height: 125px;
    overflow: hidden;
    border-radius: 6px;
    background-color: #f5f7fa;
    // 与详情页图文比例保持一致
    aspect-ratio: 16 / 10;

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

    .thumb-image {
      width: 100%;
      height: 100%;
      object-fit: cover;
      opacity: 0;
      transition: transform 0.3s ease, opacity 0.3s ease;

      &.loaded {
        opacity: 1;
      }
    }

    .thumb-category {
      position: absolute;
      top: 8px;
      left: 8px;
      padding: 2px 8px;
      font-size: 0.75rem;
      color: #fff;
      background-color: rgba(64, 158, 255, 0.9);
      border-radius: 4px;
      backdrop-filter: blur(4px);
    }
  }

  // 右侧文字信息
  .news-body {
    flex: 1;
    min-width: 0; // 保证标题省略号生效
    display: flex;
    flex-direction: column;

    .news-title-row {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      margin-bottom: 8px;

      .category-tag {
        flex-shrink: 0;
        padding: 2px 8px;
        font-size: 0.75rem;
        line-height: 1.5;
        color: #fff;
        background-color: #409eff;
        border-radius: 4px;
      }

      .news-title {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
        color: #1f2329;
        line-height: 1.5;
        transition: color 0.3s ease;
        // 标题最多两行
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
    }

    .news-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 8px;
      font-size: 0.8rem;
      color: #909399;

      .meta-item {
        position: relative;
        white-space: nowrap;
      }
    }

    .news-summary {
      margin: 0 0 12px 0;
      font-size: 0.9rem;
      color: #606266;
      line-height: 1.6;
      // 摘要最多两行
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .news-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: auto;
      gap: 12px;

      .tag-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;

        .tag-item {
          padding: 2px 8px;
          font-size: 0.75rem;
          color: #55585e;
          background-color: #f0f1f3;
          border-radius: 3px;
        }
      }

      .share-btn {
        display: flex;
        align-items: center;
        gap: 4px;
        flex-shrink: 0;
        font-size: 0.8rem;
        color: #909399;
        transition: color 0.3s ease;

        &:hover {
          color: #409eff;
        }
      }
    }
  }
}

// 响应式布局
@media (max-width: 768px) {
  .news-card {
    padding: 12px;
    gap: 12px;

    .news-thumb {
      width: 120px;
      height: 90px;
    }

    .news-body {
      .news-title-row .news-title {
        font-size: 1rem;
      }

      .news-meta {
        gap: 10px;
        margin-bottom: 6px;

        // 小屏只保留时间
        .meta-item:not(.publish-time) {
          display: none;
        }
      }

      .news-summary {
        font-size: 0.85rem;
        -webkit-line-clamp: 1;
      }
    }
  }
}

@media (max-width: 480px) {
  .news-card {
    .news-thumb {
      width: 96px;
      height: 72px;
    }

    .news-body .news-summary {
      display: none;
    }
  }
}
</style>
