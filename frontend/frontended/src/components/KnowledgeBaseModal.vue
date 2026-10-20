<template>
  <el-dialog
    v-model="visible"
    width="640px"
    top="6vh"
    :show-close="false"
    class="kb-dialog"
    append-to-body
    @open="handleOpen"
  >
    <!-- 渐变头部 + 二次元立绘 -->
    <template #header>
      <div class="kb-header">
        <div class="kb-header-text">
          <h2 class="kb-title">
            <span class="kb-title-icon">📚</span>
            知识库
            <span class="kb-title-sub">RAG</span>
          </h2>
          <p class="kb-subtitle">上传设定集、访谈、考据资料，AI 助手会结合文档回答</p>
        </div>
        <!-- 二次元立绘 -->
        <img :src="yuluko" alt="立绘" class="kb-illustration" />
        <el-icon class="kb-close" @click="visible = false"><Close /></el-icon>
      </div>
    </template>

    <!-- 统计条 -->
    <div class="kb-stats">
      <div class="stat-item">
        <span class="stat-value">{{ stats.fileCount }}</span>
        <span class="stat-label">文件</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-value">{{ stats.totalChunks }}</span>
        <span class="stat-label">知识块</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-value">{{ embeddingLabel }}</span>
        <span class="stat-label">向量模型</span>
      </div>
    </div>

    <!-- 非语义模型提示 -->
    <el-alert
      v-if="stats.totalChunks > 0 && !stats.semantic"
      type="warning"
      :closable="false"
      show-icon
      class="kb-alert"
    >
      <template #title>
        当前使用<strong>本地兜底向量</strong>，仅支持词面匹配。
        配置 <code>DASHSCOPE_API_KEY</code> 可获得真正的语义检索。
      </template>
    </el-alert>

    <!-- 上传区 -->
    <el-upload
      class="kb-upload"
      drag
      multiple
      :auto-upload="false"
      :show-file-list="false"
      :accept="acceptAttr"
      :on-change="handleFileChange"
    >
      <div class="kb-upload-inner">
        <div class="kb-upload-orb">✨</div>
        <div class="kb-upload-text">
          把文件拖到这里，或<em>点击选择</em>
        </div>
        <div class="kb-upload-hint">
          支持 {{ supportedText }} · 单个不超过 {{ stats.maxFileSizeMb }}MB
        </div>
      </div>
    </el-upload>

    <!-- 上传进度 -->
    <div v-if="uploading" class="kb-progress">
      <div class="kb-progress-label">
        <span>正在解析并建立索引：{{ uploadingName }}</span>
        <span class="kb-progress-percent">{{ progress }}%</span>
      </div>
      <el-progress :percentage="progress" :stroke-width="8" :show-text="false" striped striped-flow />
    </div>

    <!-- 文件列表 -->
    <div class="kb-list-wrap">
      <div class="kb-list-head">
        <span>已入库文件</span>
        <el-button link :icon="Refresh" :loading="loading" @click="loadFiles">刷新</el-button>
      </div>

      <el-skeleton v-if="loading && files.length === 0" :rows="3" animated />

      <div v-else-if="files.length > 0" class="kb-list">
        <div v-for="item in files" :key="item.source" class="kb-item">
          <div class="kb-item-icon">{{ fileIcon(item.source) }}</div>
          <div class="kb-item-body">
            <div class="kb-item-name" :title="item.source">{{ item.source }}</div>
            <div class="kb-item-meta">{{ item.chunks }} 个知识块</div>
          </div>
          <el-icon class="kb-item-del" title="删除" @click="handleDelete(item.source)">
            <Delete />
          </el-icon>
        </div>
      </div>

      <el-empty v-else description="还没有知识文件" :image-size="70" />
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Close, Delete, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import yuluko from '@/assets/yuluko.jpg'
import {
  deleteKnowledgeFile,
  getKnowledgeFiles,
  getKnowledgeStats,
  uploadKnowledgeFile,
  type KnowledgeFile,
  type KnowledgeStats
} from '@/api/knowledge'

const visible = defineModel<boolean>({ required: true })

const files = ref<KnowledgeFile[]>([])
const loading = ref(false)
const uploading = ref(false)
const uploadingName = ref('')
const progress = ref(0)

const stats = ref<KnowledgeStats>({
  fileCount: 0,
  totalChunks: 0,
  embeddingProvider: '',
  semantic: false,
  chunkSize: 0,
  chunkOverlap: 0,
  maxFileSizeMb: 10
})

const supportedText = 'txt / md / pdf'
const acceptAttr = '.txt,.md,.markdown,.pdf'

/** 向量模型展示名 */
const embeddingLabel = computed(() => {
  if (!stats.value.embeddingProvider) return '—'
  return stats.value.semantic ? '语义模型' : '本地兜底'
})

const fileIcon = (name: string) => {
  const lower = name.toLowerCase()
  if (lower.endsWith('.pdf')) return '📕'
  if (lower.endsWith('.md') || lower.endsWith('.markdown')) return '📘'
  return '📄'
}

const handleOpen = () => {
  loadFiles()
}

const loadFiles = async () => {
  loading.value = true
  try {
    const [listRes, statsRes] = await Promise.all([getKnowledgeFiles(), getKnowledgeStats()])

    if (listRes.code === 200 && listRes.data) {
      files.value = listRes.data.files || []
    } else {
      ElMessage.error(listRes.message || '获取知识文件失败')
    }

    if (statsRes.code === 200 && statsRes.data) {
      stats.value = statsRes.data
    }
  } catch (error: any) {
    ElMessage.error(error.message || '知识库服务不可用，请确认 AI 服务已启动')
  } finally {
    loading.value = false
  }
}

/** el-upload 选择文件后立即上传（auto-upload 关掉，手动控制进度与错误） */
const handleFileChange = async (uploadFile: UploadFile) => {
  const raw = uploadFile.raw
  if (!raw) return

  if (uploading.value) {
    ElMessage.warning('正在处理上一个文件，请稍候')
    return
  }

  uploading.value = true
  uploadingName.value = raw.name
  progress.value = 0

  try {
    const response = await uploadKnowledgeFile(raw, (percent) => {
      // 上传完成后进入服务端处理阶段，进度停在 95% 等待返回
      progress.value = Math.min(percent, 95)
    })

    if (response.code === 200 && response.data) {
      progress.value = 100
      const data = response.data
      ElMessage.success(
        `「${data.filename}」已入库：${data.chunks} 块，耗时 ${data.elapsedMs}ms`
      )
      await loadFiles()
    } else {
      ElMessage.error(response.message || '建立索引失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '上传失败')
  } finally {
    uploading.value = false
    uploadingName.value = ''
    progress.value = 0
  }
}

const handleDelete = async (filename: string) => {
  try {
    await ElMessageBox.confirm(
      `确定要从知识库移除「${filename}」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return // 用户取消
  }

  try {
    const response = await deleteKnowledgeFile(filename)
    if (response.code === 200) {
      ElMessage.success(`已移除「${filename}」`)
      await loadFiles()
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '删除失败')
  }
}
</script>

<style scoped lang="scss">
/* 主题色：与站点的梦幻紫粉渐变呼应 */
$kb-primary: #8b5cf6;
$kb-accent: #ec4899;

.kb-dialog {
  :deep(.el-dialog) {
    border-radius: 18px;
    overflow: hidden;
    background: linear-gradient(160deg, #ffffff 0%, #fdf4ff 100%);
    box-shadow: 0 18px 50px rgba(139, 92, 246, 0.25);
  }

  :deep(.el-dialog__header) {
    padding: 0;
    margin: 0;
  }

  :deep(.el-dialog__body) {
    padding: 18px 22px 22px;
  }
}

/* ==================== 头部 ==================== */
.kb-header {
  position: relative;
  padding: 20px 24px 26px;
  background: linear-gradient(120deg, #a78bfa 0%, #8b5cf6 45%, #ec4899 100%);
  overflow: hidden;

  /* 星点装饰 */
  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background-image: radial-gradient(rgba(255, 255, 255, 0.55) 1px, transparent 1px),
      radial-gradient(rgba(255, 255, 255, 0.35) 1px, transparent 1px);
    background-size: 26px 26px, 40px 40px;
    background-position: 0 0, 13px 17px;
    opacity: 0.5;
    pointer-events: none;
  }

  .kb-header-text {
    position: relative;
    z-index: 2;
    max-width: 62%;
  }

  .kb-title {
    margin: 0 0 6px;
    font-size: 1.5rem;
    font-weight: 700;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 8px;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);

    .kb-title-icon {
      font-size: 1.4rem;
    }

    .kb-title-sub {
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 1px;
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.25);
      border: 1px solid rgba(255, 255, 255, 0.5);
    }
  }

  .kb-subtitle {
    margin: 0;
    font-size: 0.83rem;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.92);
  }

  /* 二次元立绘 */
  .kb-illustration {
    position: absolute;
    right: 8px;
    bottom: -6px;
    height: 118px;
    width: auto;
    object-fit: contain;
    z-index: 1;
    filter: drop-shadow(0 6px 12px rgba(0, 0, 0, 0.22));
    pointer-events: none;
    /* 让立绘自然融入渐变背景 */
    mask-image: linear-gradient(to bottom, #000 78%, transparent 100%);
    -webkit-mask-image: linear-gradient(to bottom, #000 78%, transparent 100%);
  }

  .kb-close {
    position: absolute;
    top: 14px;
    right: 14px;
    z-index: 3;
    font-size: 18px;
    color: #fff;
    cursor: pointer;
    opacity: 0.85;
    transition: transform 0.2s ease, opacity 0.2s ease;

    &:hover {
      opacity: 1;
      transform: rotate(90deg);
    }
  }
}

/* ==================== 统计条 ==================== */
.kb-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 16px 0 14px;
  padding: 12px 16px;
  border-radius: 12px;
  background: linear-gradient(120deg, rgba(167, 139, 250, 0.12), rgba(236, 72, 153, 0.1));
  border: 1px solid rgba(139, 92, 246, 0.18);

  .stat-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }

  .stat-value {
    font-size: 1.05rem;
    font-weight: 700;
    color: $kb-primary;
  }

  .stat-label {
    font-size: 0.72rem;
    color: #7c7c8a;
  }

  .stat-divider {
    width: 1px;
    height: 26px;
    background: rgba(139, 92, 246, 0.2);
  }
}

.kb-alert {
  margin-bottom: 14px;
  border-radius: 10px;

  code {
    padding: 1px 5px;
    border-radius: 4px;
    background: rgba(0, 0, 0, 0.06);
    font-size: 0.78rem;
  }
}

/* ==================== 上传区 ==================== */
.kb-upload {
  :deep(.el-upload) {
    width: 100%;
  }

  :deep(.el-upload-dragger) {
    padding: 22px 16px;
    border: 2px dashed rgba(139, 92, 246, 0.4);
    border-radius: 14px;
    background: linear-gradient(150deg, #faf5ff 0%, #fff1f7 100%);
    transition: all 0.28s ease;

    &:hover {
      border-color: $kb-accent;
      background: linear-gradient(150deg, #f5edff 0%, #ffe9f4 100%);
      transform: translateY(-2px);
      box-shadow: 0 10px 24px rgba(139, 92, 246, 0.16);
    }
  }

  .kb-upload-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }

  .kb-upload-orb {
    font-size: 26px;
    animation: kb-float 2.6s ease-in-out infinite;
  }

  .kb-upload-text {
    font-size: 0.92rem;
    color: #5b5568;

    em {
      font-style: normal;
      font-weight: 700;
      color: $kb-accent;
    }
  }

  .kb-upload-hint {
    font-size: 0.75rem;
    color: #9a94a8;
  }
}

@keyframes kb-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-5px);
  }
}

/* ==================== 进度 ==================== */
.kb-progress {
  margin-top: 14px;

  .kb-progress-label {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: #6b6478;
    margin-bottom: 6px;
  }

  .kb-progress-percent {
    font-weight: 700;
    color: $kb-primary;
  }
}

/* ==================== 文件列表 ==================== */
.kb-list-wrap {
  margin-top: 18px;

  .kb-list-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 0.86rem;
    font-weight: 600;
    color: #4c4658;
  }

  .kb-list {
    max-height: 210px;
    overflow-y: auto;
    padding-right: 4px;
  }

  .kb-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 12px;
    margin-bottom: 7px;
    border-radius: 10px;
    background: #fff;
    border: 1px solid rgba(139, 92, 246, 0.14);
    transition: all 0.22s ease;

    &:hover {
      border-color: rgba(236, 72, 153, 0.4);
      box-shadow: 0 6px 16px rgba(139, 92, 246, 0.12);
      transform: translateX(2px);
    }

    .kb-item-icon {
      font-size: 18px;
      flex-shrink: 0;
    }

    .kb-item-body {
      flex: 1;
      min-width: 0;
    }

    .kb-item-name {
      font-size: 0.85rem;
      color: #3d3849;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .kb-item-meta {
      font-size: 0.72rem;
      color: #9a94a8;
    }

    .kb-item-del {
      flex-shrink: 0;
      font-size: 15px;
      color: #b9b3c4;
      cursor: pointer;
      transition: color 0.2s ease;

      &:hover {
        color: #f56c6c;
      }
    }
  }
}
</style>
