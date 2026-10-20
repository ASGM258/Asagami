import type { ApiResponse, PageResponse } from '@/types'
import type { NewsItem, NewsDetail, NewsListQueryParams, NewsDetailQueryRequest, NewsCategory } from '@/types/news'

/**
 * 资讯接口走 Python 资讯服务（FastAPI，默认 5000 端口），
 * 其余业务接口仍走 Java 后端（见 utils/request.ts）。
 *
 * Python 服务返回的统一外壳为：
 *   成功: { success: true, message?: string, data?: any, timestamp?: number }
 *   失败: { success: false, error: { message, code, timestamp } }
 * 这里转换为前端统一格式 { code, message, data, timestamp }，
 * 与 api/chat.ts 的处理方式保持一致。
 */
const PYTHON_API_URL = import.meta.env.VITE_PYTHON_API_URL || 'http://localhost:5000/api'

/**
 * 获取资讯列表（分页，供无限滚动逐页加载）
 */
export const getNewsList = (params: NewsListQueryParams): Promise<ApiResponse<PageResponse<NewsItem>>> => {
  return fetchApi<PageResponse<NewsItem>>('/news/list', {
    method: 'GET',
    params: params as unknown as Record<string, unknown>
  })
}

/**
 * 获取资讯详情（包含正文）
 * 参考 getAnimeDetail 的模式，支持直接传入 newsId 或请求对象
 */
export const getNewsDetail = (newsIdOrRequest: number | NewsDetailQueryRequest): Promise<ApiResponse<NewsDetail>> => {
  const newsId = typeof newsIdOrRequest === 'number' ? newsIdOrRequest : newsIdOrRequest.newsId
  return fetchApi<NewsDetail>('/news/detail', {
    method: 'POST',
    body: { newsId }
  })
}

/**
 * 获取资讯分类列表（用于列表顶部筛选标签）
 */
export const getNewsCategories = (): Promise<ApiResponse<NewsCategory[]>> => {
  return fetchApi<NewsCategory[]>('/news/categories', { method: 'GET' })
}

/**
 * 手动触发资讯抓取工作流（抓取 → 翻译 → 摘要 → 审核）
 * 服务端异步执行，立即返回受理结果
 *
 * @param limit 本次抓取条数上限
 * @param repair 是否顺带修复已入库但正文残缺的条目
 */
export const refreshNews = (
  limit?: number,
  repair?: boolean
): Promise<ApiResponse<{ accepted: boolean; message: string }>> => {
  return fetchApi<{ accepted: boolean; message: string }>('/news/refresh', {
    method: 'POST',
    params: {
      ...(limit ? { limit } : {}),
      ...(repair ? { repair: true } : {})
    }
  })
}

/** 抓取任务状态 */
export interface NewsRefreshStatus {
  running: boolean
  startedAt?: string | null
  finishedAt?: string | null
  lastRun?: {
    run_id?: string
    total?: number
    published?: number
    rejected?: number
    repair?: boolean
  } | null
}

/**
 * 查询抓取任务状态
 *
 * 前端点击「抓取」后轮询此接口，等 running=false 再刷新列表，
 * 否则用户会以为按钮没反应（一次抓取要跑抓取+补全+多次模型调用）。
 */
export const getRefreshStatus = (): Promise<ApiResponse<NewsRefreshStatus>> => {
  return fetchApi<NewsRefreshStatus>('/news/refresh/status', { method: 'GET' })
}

// ==================== 内部工具 ====================

interface FetchOptions {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  params?: Record<string, unknown>
  body?: unknown
}

/**
 * Python 服务通用请求封装
 *
 * 与 api/chat.ts 的 fetchApi 行为一致：附加 JWT、拼接查询串、
 * 把 Python 的统一外壳转换为前端 ApiResponse。
 */
async function fetchApi<T>(path: string, options: FetchOptions): Promise<ApiResponse<T>> {
  const token = localStorage.getItem('accessToken')

  // 过滤空值参数，避免向后端传递 undefined
  const search = new URLSearchParams()
  if (options.params) {
    Object.entries(options.params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        search.append(key, String(value))
      }
    })
  }
  const query = search.toString()
  const url = `${PYTHON_API_URL}${path}${query ? `?${query}` : ''}`

  try {
    const response = await fetch(url, {
      method: options.method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {})
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const backendData = await response.json()

    if (backendData.success) {
      return {
        code: 200,
        message: backendData.message || '操作成功',
        data: backendData.data ?? null,
        timestamp: backendData.timestamp || Date.now()
      }
    }

    // 失败响应：把后端 code 字符串映射为前端响应码
    const errorInfo = backendData.error || {}
    return {
      code: mapErrorCode(errorInfo.code) || response.status || 500,
      message: errorInfo.message || backendData.message || '操作失败',
      data: null,
      timestamp: errorInfo.timestamp || backendData.timestamp || Date.now()
    }
  } catch (error: any) {
    throw error
  }
}

/**
 * 将后端错误码字符串映射为前端响应码
 */
function mapErrorCode(code?: string): number | undefined {
  if (!code) return undefined

  const codeMap: Record<string, number> = {
    MISSING_PARAMETER: 400,
    INVALID_PARAMETER: 400,
    EMPTY_QUESTION: 400,
    EMPTY_TITLE: 400,
    UNAUTHORIZED: 401,
    FORBIDDEN: 403,
    NOT_FOUND: 404,
    NEWS_NOT_FOUND: 404,
    SESSION_NOT_FOUND: 404,
    SESSION_UPDATE_FAILED: 404,
    INTERNAL_SERVER_ERROR: 500,
    AI_SERVICE_ERROR: 500,
    SESSION_CREATE_FAILED: 500,
    SESSION_DELETE_FAILED: 500,
    SERVICE_UNAVAILABLE: 503
  }

  return codeMap[code]
}
