import api from '@/utils/request'
import type { ApiResponse } from '@/types'

// Python后端地址：从环境变量读取，默认5000端口
const PYTHON_API_URL = import.meta.env.VITE_PYTHON_API_URL || 'http://localhost:5000/api'

// 会话相关类型
export interface CreateSessionRequest {
  user_id: number
  title?: string
}

export interface CreateSessionResponse {
  success: boolean
  session_id: string
  title: string
  created_at: number
}

export interface SessionInfo {
  session_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface SessionsResponse {
  success: boolean
  sessions: SessionInfo[]
  count: number
}

export interface ChatMessage {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface MessagesResponse {
  success: boolean
  session_id: string
  messages: ChatMessage[]
  count: number
}

export interface UpdateTitleRequest {
  title: string
}

export interface SSEDataChunk {
  success: boolean
  chunk: string
  type: 'content' | 'end' | 'error' | 'thinking' | 'retract'
  error?: string
  is_anime_related?: boolean
  session_id?: string
  message_id?: string
  /** thinking 事件的阶段：thinking（等待模型续写）| reasoning（思维链）| tool（正在调用工具） */
  stage?: 'thinking' | 'reasoning' | 'tool'
  /** stage=tool 时的工具名 */
  tool?: string
}

/** 思考状态提示 */
export interface ThinkingState {
  stage: 'thinking' | 'reasoning' | 'tool'
  tool?: string
}

/** 流式回调集合 */
export interface StreamCallbacks {
  onChunk?: (chunk: string) => void
  onEnd?: (sessionId?: string, messageId?: string) => void
  onError?: (error: string, isAnimeRelated?: boolean) => void
  /** 进入思考/工具调用阶段：前端可显示转圈提示 */
  onThinking?: (state: ThinkingState) => void
  /**
   * 撤回此前已显示的内容
   *
   * 当前后端策略已不再发出 retract（过渡语会直接展示），
   * 回调保留仅用于兼容，收到时仍按"清空当前气泡"处理。
   */
  onRetract?: () => void
}

/**
 * 创建新会话
 */
export const createSession = (data: CreateSessionRequest): Promise<ApiResponse<CreateSessionResponse>> => {
  return fetchApi('/session/create', {
    method: 'POST',
    body: JSON.stringify(data)
  })
}

/**
 * 获取用户会话列表
 */
export const getSessions = (userId: number, limit: number = 50): Promise<ApiResponse<SessionsResponse>> => {
  return fetchApi(`/sessions?user_id=${userId}&limit=${limit}`, {
    method: 'GET'
  })
}

/**
 * 获取会话历史消息
 */
export const getSessionMessages = (sessionId: string, limit: number = 100): Promise<ApiResponse<MessagesResponse>> => {
  return fetchApi(`/session/${sessionId}/messages?limit=${limit}`, {
    method: 'GET'
  })
}

/**
 * 更新会话标题
 */
export const updateSessionTitle = (sessionId: string, data: UpdateTitleRequest): Promise<ApiResponse<{ success: boolean; message: string }>> => {
  return fetchApi(`/session/${sessionId}/title`, {
    method: 'PUT',
    body: JSON.stringify(data)
  })
}

/**
 * 删除会话
 */
export const deleteSession = (sessionId: string, hard: boolean = false): Promise<ApiResponse<{ success: boolean; message: string }>> => {
  return fetchApi(`/session/${sessionId}?hard=${hard}`, {
    method: 'DELETE'
  })
}

/**
 * 流式问答（使用Fetch API实现SSE）
 *
 * 事件类型：
 *   content  —— 文本片段（含工具调用前的过渡语），累加进当前气泡
 *   thinking —— 进入思考 / reasoning / 工具调用阶段，仅用于展示转圈提示，不含正文
 *   retract  —— 携带兼容保留，后端当前不再发出
 *   end      —— 传输完成，携带 session_id / message_id
 *   error    —— 错误或非动漫问题
 *
 * 说明：后端会过滤掉 ToolMessage 的原始数据与模型的 reasoning，
 *       因此 content 里的内容都可以直接展示。
 *       为兼容旧调用方式，前三个参数保持原有的三个可选回调顺序不变。
 */
export const streamChat = async (
  question: string,
  userId: number,
  sessionId?: string,
  onChunk?: (chunk: string) => void,
  onEnd?: (sessionId?: string, messageId?: string) => void,
  onError?: (error: string, isAnimeRelated?: boolean) => void,
  onThinking?: (state: ThinkingState) => void,
  onRetract?: () => void
): Promise<void> => {
  try {
    const response = await fetch(`${PYTHON_API_URL}/anime-chat-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
      },
      body: JSON.stringify({
        question,
        user_id: userId,
        session_id: sessionId
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      
      if (done) break

      // 解码并解析SSE格式
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || '' // 保留不完整的最后一行

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonData = line.slice(6) // 去掉 'data: ' 前缀
          
          try {
            const data: SSEDataChunk = JSON.parse(jsonData)
            
            if (data.type === 'content' && data.success) {
              // 文本片段（含过渡语）：直接累加进当前气泡
              if (onChunk) {
                onChunk(data.chunk)
              }
            } else if (data.type === 'thinking') {
              // 思考 / reasoning / 工具调用阶段：仅展示提示，不追加正文
              if (onThinking) {
                onThinking({
                  stage:
                    data.stage === 'tool'
                      ? 'tool'
                      : data.stage === 'reasoning'
                        ? 'reasoning'
                        : 'thinking',
                  tool: data.tool
                })
              }
            } else if (data.type === 'retract') {
              // 兼容保留：后端当前不再发出
              if (onRetract) {
                onRetract()
              }
            } else if (data.type === 'end') {
              // 传输完成
              if (onEnd) {
                onEnd(data.session_id, data.message_id)
              }
              return
            } else if (data.type === 'error') {
              // 错误处理
              if (onError) {
                onError(data.error || '未知错误', data.is_anime_related)
              }
              
              // 如果是非动漫相关问题，不抛出异常
              if (data.is_anime_related === false) {
                return
              }
              throw new Error(data.error || '系统错误')
            }
          } catch (e) {
            // 解析SSE数据失败，静默处理
          }
        }
      }
    }
  } catch (error: any) {
    if (onError) {
      onError(error.message || '网络请求失败')
    }
    throw error
  }
}

/**
 * 非流式问答（备用）
 */
export const chat = (question: string, userId: number, sessionId?: string): Promise<ApiResponse<{
  success: boolean
  answer: string
  is_anime_related: boolean
  user_id: number
  timestamp: number
  session_id?: string
  message_id?: string
}>> => {
  return fetchApi('/anime-chat', {
    method: 'POST',
    body: JSON.stringify({
      question,
      user_id: userId,
      session_id: sessionId
    })
  })
}

/**
 * 通用Fetch API封装（用于Python后端）
 */
async function fetchApi<T = any>(path: string, options: RequestInit): Promise<ApiResponse<T>> {
  try {
    const token = localStorage.getItem('accessToken')
    
    const response = await fetch(`${PYTHON_API_URL}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...options.headers
      }
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const backendData = await response.json()
    
    // Python后端返回格式有两种：
    // 成功: { success: true, message?: string, data?: any, timestamp?: number }
    // 失败: { success: false, error: { message: string, code: string, timestamp: number } }
    // 转换为前端统一格式: { code: number, message: string, data: any, timestamp: number }
    
    if (backendData.success) {
      // 成功响应
      return {
        code: 200,
        message: backendData.message || '操作成功',
        data: backendData.data || null,
        timestamp: backendData.timestamp || Date.now()
      }
    } else {
      // 失败响应 - 处理error对象
      const errorInfo = backendData.error || {}
      return {
        code: mapErrorCode(errorInfo.code) || (response.status || 500),
        message: errorInfo.message || backendData.message || '操作失败',
        data: null,
        timestamp: errorInfo.timestamp || backendData.timestamp || Date.now()
      }
    }
  } catch (error: any) {
    // API请求失败，抛出错误由调用方处理
    throw error
  }
}

/**
 * 将后端错误码映射为前端响应码
 */
function mapErrorCode(code?: string): number | undefined {
  if (!code) return undefined
  
  const codeMap: Record<string, number> = {
    'MISSING_PARAMETER': 400,
    'INVALID_PARAMETER': 400,
    'UNAUTHORIZED': 401,
    'FORBIDDEN': 403,
    'NOT_FOUND': 404,
    'INTERNAL_SERVER_ERROR': 500,
    'SERVICE_UNAVAILABLE': 503
  }
  
  return codeMap[code]
}
