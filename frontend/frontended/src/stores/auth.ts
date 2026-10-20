import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, register as registerApi, getProfile as getProfileApi } from '@/api/auth'
import type { LoginRequest, RegisterRequest, AuthResponse, UserInfo } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const token = ref<string>(localStorage.getItem('accessToken') || '')
  const userInfo = ref<UserInfo | null>(null)
  const isLoggedIn = ref<boolean>(!!localStorage.getItem('accessToken'))

  // 登录
  const login = async (loginData: LoginRequest) => {
    try {
      const response = await loginApi(loginData)
      
      if (response.code === 200 && response.data) {
        const authData = response.data as AuthResponse
        
        // 保存 Token 和用户信息
        token.value = authData.accessToken
        userInfo.value = {
          id: authData.userId,
          username: authData.username,
          email: authData.email,
          password: null,
          avatar: authData.avatar,
          nickname: authData.nickname,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        }
        isLoggedIn.value = true
        
        // 持久化到 localStorage
        localStorage.setItem('accessToken', authData.accessToken)
        localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
        
        return { success: true, message: response.message }
      } else {
        return { success: false, message: response.message }
      }
    } catch (error: any) {
      return { success: false, message: error.message || '登录失败' }
    }
  }

  // 注册
  const register = async (registerData: RegisterRequest) => {
    try {
      const response = await registerApi(registerData)
      
      if (response.code === 200 && response.data) {
        const authData = response.data as AuthResponse
        
        // 保存 Token 和用户信息
        token.value = authData.accessToken
        userInfo.value = {
          id: authData.userId,
          username: authData.username,
          email: authData.email,
          password: null,
          avatar: authData.avatar,
          nickname: authData.nickname,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        }
        isLoggedIn.value = true
        
        // 持久化到 localStorage
        localStorage.setItem('accessToken', authData.accessToken)
        localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
        
        return { success: true, message: response.message }
      } 
      else {
        return { success: false, message: response.message }
      }
    } catch (error: any) {
      return { success: false, message: error.message || '注册失败' }
    }
  }

  // 获取用户信息
  const fetchUserInfo = async () => {
    try {
      const response = await getProfileApi()
      
      if (response.code === 200 && response.data) {
        userInfo.value = response.data
        localStorage.setItem('userInfo', JSON.stringify(response.data))
        return { success: true }
      } else {
        return { success: false, message: response.message }
      }
    } catch (error: any) {
      return { success: false, message: error.message || '获取用户信息失败' }
    }
  }

  // 登出
  const logout = () => {
    token.value = ''
    userInfo.value = null
    isLoggedIn.value = false
    
    // 清除本地存储
    localStorage.removeItem('accessToken')
    localStorage.removeItem('userInfo')
  }

  // 初始化 - 从 localStorage 恢复状态
  const initAuth = () => {
    const storedToken = localStorage.getItem('accessToken')
    const storedUserInfo = localStorage.getItem('userInfo')
    
    if (storedToken && storedUserInfo) {
      token.value = storedToken
      userInfo.value = JSON.parse(storedUserInfo)
      isLoggedIn.value = true
    }
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    login,
    register,
    fetchUserInfo,
    logout,
    initAuth
  }
})
