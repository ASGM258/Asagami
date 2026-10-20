import type { ApiResponse } from '@/types'

/**
 * 知识库（RAG）接口 —— 走 Python AI 服务
 *
 * ⚠️ 不能复用 chat.ts / news.ts 里的 fetchApi：那些封装把 headers 固定成
 * `Content-Type: application/json`，会破坏 multipart/form-data 上传
 * （浏览器需要自己生成带 boundary 的 Content-Type）。
 * 因此这里单独实现，上传时不设置 Content-Type。
 */
const PYTHON_API_URL = import.meta.env.VITE_PYTHON_API_URL || 'http://localhost:5000/api'

/** 上传结果 */
export interface KnowledgeUploadResult {
  filename: string
  chars: number
  chunks: number
  stored: number
  elapsedMs: number
  embeddingProvider: string
  semantic: boolean
}

/** 已入库文件 */
export interface KnowledgeFile {
  source: string
  chunks: number
}

/** 文件列表响应 */
export interface KnowledgeFileList {
  files: KnowledgeFile[]
  count: number
  totalChunks: number
  embeddingProvider: string
  semantic: boolean
  supportedExtensions: string[]
}

/** 知识库统计 */
export interface KnowledgeStats {
  fileCount: number
  totalChunks: number
  embeddingProvider: string
  semantic: boolean
  chunkSize: number
  chunkOverlap: number
  maxFileSizeMb: number
}

/**
 * 上传知识文件（txt / md / pdf）
 *
 * @param file 待上传文件
 * @param onProgress 上传进度回调（0-100，浏览器能拿到总大小时才触发）
 */
export const uploadKnowledgeFile = (
  file: File,
  onProgress?: (percent: number) => void
): Promise<ApiResponse<KnowledgeUploadResult>> => {
  return new Promise((resolve, reject) => {
    const formData = new FormData()
    formData.append('file', file)

    const token = localStorage.getItem('accessToken')

    // 用 XHR 而非 fetch：需要真实的上传进度
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${PYTHON_API_URL}/knowledge/upload`)
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    }
    // 注意：不要设置 Content-Type，交给浏览器带 boundary

    xhr.upload.onprogress = (event) => {
      if (onProgress && event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }

    xhr.onload = () => {
      let payload: any = null
      try {
        payload = JSON.parse(xhr.responseText)
      } catch {
        reject(new Error(`服务返回了非 JSON 内容（HTTP ${xhr.status}）`))
        return
      }
      resolve(toApiResponse(payload, xhr.status))
    }

    xhr.onerror = () => reject(new Error('网络请求失败，请确认 AI 服务已启动'))
    xhr.ontimeout = () => reject(new Error('上传超时'))
    xhr.timeout = 180000 // 大文件向量化可能较慢

    xhr.send(formData)
  })
}

/** 已入库文件列表 */
export const getKnowledgeFiles = (): Promise<ApiResponse<KnowledgeFileList>> => {
  return fetchApi<KnowledgeFileList>('/knowledge/files', { method: 'GET' })
}

/** 删除某个文件的知识 */
export const deleteKnowledgeFile = (
  filename: string
): Promise<ApiResponse<{ filename: string; removedChunks: number }>> => {
  return fetchApi(`/knowledge/files?filename=${encodeURIComponent(filename)}`, {
    method: 'DELETE'
  })
}

/** 知识库统计 */
export const getKnowledgeStats = (): Promise<ApiResponse<KnowledgeStats>> => {
  return fetchApi<KnowledgeStats>('/knowledge/stats', { method: 'GET' })
}

// ==================== 内部工具 ====================

/** 普通 JSON 请求（与 news.ts 的封装同构） */
async function fetchApi<T>(path: string, options: RequestInit): Promise<ApiResponse<T>> {
  const token = localStorage.getItem('accessToken')

  const response = await fetch(`${PYTHON_API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  })

  const payload = await response.json().catch(() => null)
  if (payload === null) {
    throw new Error(`服务返回了非 JSON 内容（HTTP ${response.status}）`)
  }
  return toApiResponse<T>(payload, response.status)
}

/**
 * 把 Python 服务的统一外壳转成前端 ApiResponse
 *
 * 成功: { success: true, message, data, timestamp }
 * 失败: { success: false, error: { message, code, timestamp } }
 */
function toApiResponse<T>(payload: any, httpStatus: number): ApiResponse<T> {
  if (payload?.success) {
    return {
      code: 200,
      message: payload.message || '操作成功',
      data: payload.data ?? null,
      timestamp: payload.timestamp || Date.now()
    }
  }

  const error = payload?.error || {}
  return {
    code: mapErrorCode(error.code) || httpStatus || 500,
    message: error.message || payload?.message || '操作失败',
    data: null,
    timestamp: error.timestamp || Date.now()
  }
}

/** 后端错误码 → 前端响应码 */
function mapErrorCode(code?: string): number | undefined {
  if (!code) return undefined

  const codeMap: Record<string, number> = {
    MISSING_PARAMETER: 400,
    INVALID_PARAMETER: 400,
    UNSUPPORTED_FILE_TYPE: 400,
    DOCUMENT_PARSE_FAILED: 400,
    EMPTY_FILE: 400,
    FILE_TOO_LARGE: 413,
    UNAUTHORIZED: 401,
    FORBIDDEN: 403,
    NOT_FOUND: 404,
    KNOWLEDGE_NOT_FOUND: 404,
    INTERNAL_SERVER_ERROR: 500,
    INGEST_FAILED: 500,
    SERVICE_UNAVAILABLE: 503
  }

  return codeMap[code]
}
