import api from '@/utils/request'
import type {
  LoginRequest,
  RegisterRequest,
  UpdateProfileRequest,
  ApiResponse,
  AuthResponse,
  UserInfo
} from '@/types/auth'

/**
 * 用户登录
 */
export const login = (data: LoginRequest): Promise<ApiResponse<AuthResponse>> => {
  return api.post('/auth/login', data)
}

/**
 * 用户注册
 */
export const register = (data: RegisterRequest): Promise<ApiResponse<AuthResponse>> => {
  return api.post('/auth/register', data)
}

/**
 * 获取用户信息
 */
export const getProfile = (): Promise<ApiResponse<UserInfo>> => {
  return api.get('/auth/profile')
}

/**
 * 更新用户信息
 */
export const updateProfile = (data: UpdateProfileRequest): Promise<ApiResponse<UserInfo>> => {
  return api.put('/auth/profile', data)
}

/**
 * 上传头像
 */
export const uploadAvatar = (file: File): Promise<ApiResponse<{ avatarUrl: string }>> => {
  const formData = new FormData()
  formData.append('avatar', file)
  return api.post('/upload/avatar', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}
