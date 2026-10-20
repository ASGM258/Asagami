// 用户相关类型定义

// 登录请求
export interface LoginRequest {
  username: string  // 用户名或邮箱
  password: string
}

// 注册请求
export interface RegisterRequest {
  username: string
  email: string
  password: string
  nickname?: string
}

// 认证响应数据
export interface AuthResponse {
  accessToken: string
  tokenType: string
  userId: number
  username: string
  email: string
  nickname: string
  avatar: string | null
}

// 用户信息
export interface UserInfo {
  id: number
  username: string
  email: string
  password: string | null
  avatar: string | null
  nickname: string
  createdAt: string
  updatedAt: string
}

// 更新用户信息请求
export interface UpdateProfileRequest {
  nickname?: string
  email?: string
  avatar?: string
  currentPassword?: string  // 当前密码（修改密码时需要）
  newPassword?: string      // 新密码（可选）
}

// 统一响应格式
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T | null
  timestamp: number
}

// 响应码常量
export const ResponseCode = {
  SUCCESS: 200,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  USER_EXISTS: 1001,
  USER_NOT_FOUND: 1002,
  LOGIN_ERROR: 1003,
  TOKEN_INVALID: 1004,
  TOKEN_EXPIRED: 1005,
  SERVER_ERROR: 500
} as const

export type ResponseCodeType = typeof ResponseCode[keyof typeof ResponseCode]
