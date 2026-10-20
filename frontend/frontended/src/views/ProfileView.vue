<template>
  <div class="profile-view">
    <!-- 主内容区 -->
    <div class="profile-main">
      <!-- 信息修改表单 -->
      <div class="form-container">
        <el-form
          ref="formRef"
          :model="profileForm"
          :rules="formRules"
          label-width="100px"
          class="profile-form"
        >
          <el-form-item label="用户名" prop="username">
            <el-input v-model="profileForm.username" disabled />
          </el-form-item>

          <el-form-item label="昵称" prop="nickname">
            <el-input v-model="profileForm.nickname" placeholder="请输入昵称" />
          </el-form-item>

          <el-form-item label="邮箱" prop="email">
            <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
          </el-form-item>

          <el-form-item label="头像" prop="avatar">
            <div class="avatar-upload">
              <!-- 头像预览 -->
              <div class="avatar-preview-container">
                <img 
                  v-if="avatarPreview || profileForm.avatar" 
                  :src="avatarPreview || profileForm.avatar" 
                  alt="avatar preview" 
                  class="avatar-image"
                />
                <div v-else class="avatar-placeholder">
                  <el-icon :size="40"><User /></el-icon>
                </div>
              </div>
              
              <!-- 上传按钮 -->
              <el-upload
                class="avatar-uploader"
                action="#"
                :auto-upload="false"
                :show-file-list="false"
                :before-upload="beforeAvatarUpload"
                @change="handleAvatarChange"
                accept="image/*"
              >
                <el-button type="primary" plain>
                  <el-icon><Upload /></el-icon>
                  选择图片
                </el-button>
              </el-upload>
              
              <div class="upload-tip">支持 jpg、png 格式，文件大小不超过 2MB</div>
            </div>
          </el-form-item>

          <el-form-item label="当前密码" prop="currentPassword">
            <el-input
              v-model="profileForm.currentPassword"
              type="password"
              placeholder="修改密码时需要填写"
              show-password
            />
          </el-form-item>

          <el-form-item label="新密码" prop="newPassword">
            <el-input
              v-model="profileForm.newPassword"
              type="password"
              placeholder="输入新密码（可选）"
              show-password
            />
          </el-form-item>

          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input
              v-model="profileForm.confirmPassword"
              type="password"
              placeholder="再次输入新密码"
              show-password
            />
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="handleSubmit" :loading="submitting">
              保存修改
            </el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { User, Upload } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { updateProfile as updateProfileApi, uploadAvatar as uploadAvatarApi } from '@/api/auth'
import type { FormInstance, FormRules, UploadUserFile } from 'element-plus'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()
const submitting = ref(false)
const formRef = ref<FormInstance>()
const avatarFile = ref<File | null>(null)
const avatarPreview = ref<string>('')

// 表单数据
const profileForm = reactive({
  username: '',
  nickname: '',
  email: '',
  avatar: '',
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

// 表单验证规则
const formRules: FormRules = {
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    { min: 2, max: 20, message: '昵称长度在 2 到 20 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  newPassword: [
    { min: 6, message: '密码长度不能少于 6 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    {
      validator: (rule, value, callback) => {
        if (value !== profileForm.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 头像上传前验证
const beforeAvatarUpload = (file: File) => {
  // 检查 MIME 类型
  const isImage = file.type.startsWith('image/')
  
  // 检查文件扩展名
  const fileName = file.name.toLowerCase()
  const validExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
  const hasValidExtension = validExtensions.some(ext => fileName.endsWith(ext))
  
  // 检查文件大小（2MB）
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isImage || !hasValidExtension) {
    ElMessage.error('只能上传图片文件（支持 jpg、png、gif、webp、bmp）！')
    return false
  }
  
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB！')
    return false
  }
  
  return true
}

// 处理头像文件选择
const handleAvatarChange = (uploadFile: UploadUserFile) => {
  if (uploadFile.raw) {
    avatarFile.value = uploadFile.raw
    // 生成预览 URL
    avatarPreview.value = URL.createObjectURL(uploadFile.raw)
  }
}

// 初始化表单数据
onMounted(() => {
  const userInfo = authStore.userInfo
  if (userInfo) {
    profileForm.username = userInfo.username
    profileForm.nickname = userInfo.nickname || ''
    profileForm.email = userInfo.email
    profileForm.avatar = userInfo.avatar || ''
  }
})

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        submitting.value = true
        
        let avatarUrl = profileForm.avatar
        
        // 如果有新选择的头像文件，先上传
        if (avatarFile.value) {
          const uploadResult = await uploadAvatarApi(avatarFile.value)
          if (uploadResult.code === 200 && uploadResult.data) {
            avatarUrl = uploadResult.data.avatarUrl
          } else {
            ElMessage.error('头像上传失败')
            return
          }
        }
        
        // 调用后端 API 更新用户信息
        const result = await updateProfileApi({
          nickname: profileForm.nickname,
          email: profileForm.email,
          avatar: avatarUrl || undefined,
          currentPassword: profileForm.currentPassword || undefined,
          newPassword: profileForm.newPassword || undefined
        })

        if (result.code === 200) {
          ElMessage.success('个人信息更新成功！')
          
          // 清空密码字段和头像文件
          profileForm.currentPassword = ''
          profileForm.newPassword = ''
          profileForm.confirmPassword = ''
          avatarFile.value = null
          avatarPreview.value = ''
          
          // 更新本地存储的用户信息
          await authStore.fetchUserInfo()
        } else {
          ElMessage.error(result.message || '更新失败')
        }
      } catch (error: any) {
        ElMessage.error(error.message || '更新失败，请稍后重试')
      } finally {
        submitting.value = false
      }
    } else {
      ElMessage.warning('请检查表单填写是否正确')
    }
  })
}

// 重置表单
const handleReset = () => {
  const userInfo = authStore.userInfo
  if (userInfo) {
    profileForm.nickname = userInfo.nickname || ''
    profileForm.email = userInfo.email
    profileForm.avatar = userInfo.avatar || ''
    profileForm.currentPassword = ''
    profileForm.newPassword = ''
    profileForm.confirmPassword = ''
  }
  formRef.value?.clearValidate()
}
</script>

<style scoped lang="scss">
.profile-view {
  height: 100vh;
  display: flex;
  background-color: rgba(255, 255, 255, 0.6);

  // 主内容区
  .profile-main {
    flex: 1;
    overflow-y: auto;
    padding: 6.25vh; /* (100vh - 87.5vh) / 2 = 6.25vh */
    display: flex;
    align-items: center;

    .form-container {
      width: 87.5%; /* 7/8 = 87.5% */
      max-width: 1200px;
      height: 87.5vh; /* 高度的 7/8 */
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      justify-content: center;

      .profile-form {
        background-color: rgba(255, 255, 255, 0.4);
        padding: 30px;
        border-radius: 8px;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);

        .avatar-preview {
          margin-top: 10px;
          width: 80px;
          height: 80px;
          border-radius: 50%;
          overflow: hidden;
          border: 2px solid #dcdfe6;

          img {
            width: 100%;
            height: 100%;
            object-fit: cover;
          }
        }

        :deep(.el-form-item) {
          margin-bottom: 22px;
        }

        :deep(.el-button) {
          margin-right: 10px;
        }

        // 头像上传样式
        .avatar-upload {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 12px;

          .avatar-preview-container {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            overflow: hidden;
            border: 3px solid #dcdfe6;
            background-color: #f5f7fa;
            display: flex;
            align-items: center;
            justify-content: center;

            .avatar-image {
              width: 100%;
              height: 100%;
              object-fit: cover;
            }

            .avatar-placeholder {
              color: #c0c4cc;
              display: flex;
              align-items: center;
              justify-content: center;
            }
          }

          .avatar-uploader {
            :deep(.el-upload) {
              border: none;
            }
          }

          .upload-tip {
            font-size: 0.85rem;
            color: #909399;
            margin-top: 4px;
          }
        }
      }
    }
  }
}
</style>
