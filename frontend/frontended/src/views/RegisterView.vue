<template>
  <div class="register-container">
    <div class="outer">
      <div class="left"></div>
      <div class="right">
        <h4>注册</h4>
        <form @submit.prevent="handleRegister">
          <input 
            class="t" 
            type="text" 
            v-model="registerForm.username" 
            placeholder="用户名"
            required
          >
          <input 
            class="t" 
            type="email" 
            v-model="registerForm.email" 
            placeholder="邮箱"
            required
          >
          <input 
            class="t" 
            type="password" 
            v-model="registerForm.password" 
            placeholder="密码"
            required
          >
          <input 
            class="t" 
            type="text" 
            v-model="registerForm.nickname" 
            placeholder="昵称（可选）"
          >
          <input 
            class="but" 
            type="submit" 
            :value="loading ? '注册中...' : 'Register'"
            :disabled="loading"
          >
          <div class="login-link">
            已有账号？<router-link to="/login">立即登录</router-link>
          </div>
          <div v-if="successMessage" class="success-message">
            {{ successMessage }}
          </div>
          <div v-if="errorMessage" class="error-message">
            {{ errorMessage }}
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import loginBg from '@/assets/login-bg.jpg'
import { useAuthStore } from '@/stores/auth'
import type { RegisterRequest } from '@/types/auth'

// 路由
const router = useRouter()

// 使用 Pinia store
const authStore = useAuthStore()

// 表单数据
const registerForm = reactive<RegisterRequest>({
  username: '',
  email: '',
  password: '',
  nickname: ''
})

// 加载状态
const loading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

// 处理注册
const handleRegister = async () => {
  // 清空消息
  errorMessage.value = ''
  successMessage.value = ''
  
  // 验证用户名
  if (!registerForm.username.trim()) {
    errorMessage.value = '请输入用户名'
    return
  }
  
  if (registerForm.username.length < 3 || registerForm.username.length > 50) {
    errorMessage.value = '用户名长度必须在3-50个字符之间'
    return
  }
  
  // 验证邮箱
  if (!registerForm.email.trim()) {
    errorMessage.value = '请输入邮箱'
    return
  }
  
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(registerForm.email)) {
    errorMessage.value = '邮箱格式不正确'
    return
  }
  
  // 验证密码
  if (!registerForm.password) {
    errorMessage.value = '请输入密码'
    return
  }
  
  if (registerForm.password.length < 6 || registerForm.password.length > 100) {
    errorMessage.value = '密码长度必须在6-100个字符之间'
    return
  }
  
  // 验证昵称（如果填写了）
  if (registerForm.nickname && registerForm.nickname.length > 50) {
    errorMessage.value = '昵称长度不能超过50个字符'
    return
  }
  
  try {
    loading.value = true
    
    const result = await authStore.register(registerForm)
    
    if (result.success) {
      console.log('注册成功！', result.message)
      successMessage.value = result.message || '注册成功！'
      
      // 注册成功后跳转到登录页
      setTimeout(() => {
        router.push('/login')
      }, 1500)
    } else {
      errorMessage.value = result.message || '注册失败'
    }
  } catch (error: any) {
    errorMessage.value = error.message || '注册失败，请稍后重试'
    console.error('注册错误:', error)
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss">
/* 全局样式重置 */
body {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

*,
*::before,
*::after {
  box-sizing: inherit;
}
</style>

<style scoped lang="scss">
.register-container {
  min-height: 100vh;
  width: 100%;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  
  // 背景渐变
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: -1;
    background: linear-gradient(120deg, #e0c3fc 0%, #8ec5fc 100%);
  }
}

.outer {
  display: flex;
  overflow: hidden;
  width: 80rem;
  height: 55rem;
  max-width: 90vw;
  max-height: 85vh;
  background-color: rgba(255, 255, 255, 0.3);
  border-radius: 1.5rem;
  box-shadow: 0 0 1rem 0.2rem rgb(0 0 0 / 10%);
}

.outer .left {
  position: relative;
  width: 40%;
  height: 100%;
  background-color: #8ec5fc;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-image: v-bind("'url(' + loginBg + ')'");
    background-size: cover;
    background-position: center;
    opacity: 0.8;
  }
}

.outer .right {
  display: flex;
  width: 60%;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;

  h4 {
    color: #6c22b0;
    font-size: 2.5rem;
    margin-bottom: 3rem;
  }

  form {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    
    .t {
      outline: none;
      width: 80%;
      height: 3.5rem;
      font-size: 1rem;
      margin: 1.5rem 0;
      padding: 0.8rem 0 0 1.5rem;
      border: none;
      border-bottom: 1px solid #d51eb7;
      color: #8ec5fc;
      background-color: rgb(0 0 0 / 0%);

      &:focus {
        outline: none;
        color: #d51eb7;
        padding: 1rem 0 0 1.3rem;
      }
    }
  }

  .error-message {
    width: 80%;
    margin-top: 1rem;
    padding: 0.8rem;
    color: #d51eb7;
    font-size: 0.9rem;
    text-align: center;
    background-color: rgba(213, 30, 183, 0.1);
    border-radius: 0.3rem;
  }

  .but {
    width: 60%;
    height: 4rem;
    color: #d51eb7;
    background-color: #8ec5fc;
    border: none;
    font-size: 1.3rem;
    margin-top: 2rem;
    cursor: pointer;
    transition: all 0.3s ease;
    border-radius: 0.5rem;

    &:hover:not(:disabled) {
      background-color: #7ab4ed;
      transform: scale(1.05);
    }

    &:active:not(:disabled) {
      transform: scale(0.98);
    }

    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }

  .login-link {
    width: 80%;
    margin-top: 1.5rem;
    text-align: left;
    font-size: 1rem;
    color: #6c22b0;
    
    a {
      color: #d51eb7;
      text-decoration: none;
      font-weight: 500;
      transition: all 0.3s ease;
      
      &:hover {
        color: #6c22b0;
        text-decoration: underline;
      }
    }
  }

  .success-message {
    width: 80%;
    margin-top: 1rem;
    padding: 0.8rem;
    color: #28a745;
    font-size: 0.9rem;
    text-align: center;
    background-color: rgba(40, 167, 69, 0.1);
    border-radius: 0.3rem;
  }
}

// 响应式设计
@media (max-width: 768px) {
  .outer {
    width: 90%;
    height: auto;
    flex-direction: column;
    margin: 5% auto;

    .left {
      width: 100%;
      height: 20rem;
    }

    .right {
      width: 100%;
      padding: 2rem;
    }
  }
}
</style>
