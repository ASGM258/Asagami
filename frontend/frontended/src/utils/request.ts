import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse, AxiosError } from 'axios'
import type { ApiResponse } from '@/types/auth'
import router from '@/router'
import { ElMessage } from 'element-plus'

// 创建 axios 实例
const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8081/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 自动添加 Token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('accessToken')
    if (token) {
      // 使用 set 方法设置 Authorization 头，确保正确添加
      config.headers.set('Authorization', `Bearer ${token}`)
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理统一响应格式和 Token 过期
api.interceptors.response.use(
  (response: AxiosResponse): any => {
    const responseData = response.data as ApiResponse
    
    // 检查业务逻辑错误码（Token过期或无效）
    if (responseData.code === 1004 || responseData.code === 1005) {
      // Token 过期或无效，清除本地数据
      localStorage.removeItem('accessToken')
      localStorage.removeItem('userInfo')
      
      // 使用 Vue Router 跳转到登录页，保留当前路径
      const currentPath = window.location.pathname + window.location.search
      
      // 避免重复跳转
      if (!currentPath.includes('/login')) {
        router.push({
          path: '/login',
          query: { redirect: currentPath }
        }).catch(err => {
          // 路由跳转失败，静默处理
        })
        
        // 显示友好提示
        ElMessage.warning('登录已过期，请重新登录')
      }
      
      // 抛出错误，阻止继续处理
      return Promise.reject(new Error(responseData.message || '登录已过期，请重新登录'))
    }
    
    // 直接返回 data 部分，简化调用方的使用
    return responseData
  },
  (error: AxiosError<ApiResponse>) => {
    // 处理 HTTP 层面的错误（如 401）
    const errorCode = error.response?.data?.code
    const status = error.response?.status
    
    if (errorCode === 1004 || 
        errorCode === 1005 ||
        status === 401) {
      // Token 过期或无效，清除本地数据
      localStorage.removeItem('accessToken')
      localStorage.removeItem('userInfo')
      
      // 使用 Vue Router 跳转到登录页，保留当前路径
      const currentPath = window.location.pathname + window.location.search
      
      // 避免重复跳转
      if (!currentPath.includes('/login')) {
        router.push({
          path: '/login',
          query: { redirect: currentPath }
        }).catch(err => {
          // 路由跳转失败，静默处理
        })
        
        // 显示友好提示
        ElMessage.warning('登录已过期，请重新登录')
      }
      
      return Promise.reject(new Error(error.response?.data?.message || '登录已过期，请重新登录'))
    }
    
    // 处理其他错误
    const message = error.response?.data?.message || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

export default api
