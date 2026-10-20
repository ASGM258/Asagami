<template>
  <div class="chat-view">
    <div class="chat-container">
      <!-- 左侧会话列表 -->
      <div class="sidebar">
        <div class="sidebar-header">
          <el-button type="primary" @click="handleCreateNewSession" :icon="Plus">
            新建会话
          </el-button>
        </div>
        
        <div class="session-list">
          <div 
            v-for="session in sessions" 
            :key="session.session_id"
            class="session-item"
            :class="{ active: currentSession?.session_id === session.session_id }"
            @click="loadSession(session.session_id)"
          >
            <div class="session-info">
              <el-icon><ChatDotRound /></el-icon>
              <span class="session-title">{{ session.title }}</span>
            </div>
            <el-dropdown trigger="click" @command="(cmd: string) => handleSessionCommand(cmd, session.session_id)">
              <el-icon class="session-more"><MoreFilled /></el-icon>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="rename">重命名</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          
          <el-empty v-if="sessions.length === 0" description="暂无会话" :image-size="80" />
        </div>
      </div>

      <!-- 右侧聊天区域 -->
      <div class="chat-area">
        <!-- 消息列表 -->
        <div class="messages-container" ref="messagesContainer">
          <div v-if="messages.length === 0 && !loading" class="welcome-message">
            <div class="welcome-icon">🎌</div>
            <h2>欢迎来到动漫AI助手</h2>
            <p>我可以帮你：</p>
            <ul>
              <li>推荐好看的动漫</li>
              <li>查询你的追番历史</li>
              <li>回答动漫相关问题</li>
              <li>提供观看建议</li>
            </ul>
          </div>

          <div 
            v-for="(msg, index) in messages" 
            :key="index"
            class="message"
            :class="msg.role"
          >
            <div class="message-avatar">
              <!-- 用户头像 -->
              <el-avatar v-if="msg.role === 'user'" :size="40" :src="authStore.userInfo?.avatar || undefined">
                {{ authStore.userInfo?.nickname?.charAt(0) || '用' }}
              </el-avatar>
              <!-- AI头像 -->
              <el-avatar v-else :size="40" class="ai-avatar">
                🤖
              </el-avatar>
            </div>
            
            <div class="message-content">
              <!-- 用户昵称或AI助手 -->
              <div class="message-role">{{ msg.role === 'user' ? (authStore.userInfo?.nickname || '你') : 'AI助手' }}</div>
              <!-- AI回复使用分段展示 -->
              <div v-if="msg.role === 'assistant'" class="message-text" v-html="toSafeHtml(msg.content)"></div>
              <!-- 用户消息保持原样 -->
              <div v-else class="message-text">{{ msg.content }}</div>

              <!-- 思考/工具调用提示：仅在最后一条未完成的 AI 消息上显示 -->
              <div
                v-if="msg.role === 'assistant' && !msg.completed && thinkingState"
                class="thinking-hint"
              >
                <el-icon class="thinking-icon is-loading"><Loading /></el-icon>
                <span class="thinking-text">{{ thinkingText }}<span class="thinking-dots"></span></span>
              </div>
            </div>
          </div>

          <!-- 加载状态 -->
          <div v-if="loading" class="loading-message">
            <div class="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="input-area">
          <div class="input-wrapper">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="3"
              placeholder="输入你的问题...（Enter发送，Shift+Enter换行）"
              :disabled="sending"
              @keydown.enter.exact.prevent="handleSend"
              @keydown.enter.shift.exact="inputMessage += '\n'"
            />
            <div class="input-actions">
              <span class="tip-text">AI助手基于DeepSeek模型</span>
              <el-button 
                type="primary" 
                @click="handleSend" 
                :disabled="!inputMessage.trim() || sending"
                :loading="sending"
              >
                <el-icon v-if="!sending"><Promotion /></el-icon>
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 重命名对话框 -->
    <el-dialog
      v-model="renameDialogVisible"
      title="重命名会话"
      width="400px"
    >
      <el-input
        v-model="newTitle"
        placeholder="请输入新的会话标题"
        maxlength="50"
        show-word-limit
      />
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRenameConfirm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  createSession,
  getSessions,
  getSessionMessages,
  updateSessionTitle,
  deleteSession,
  streamChat,
  type SessionInfo,
  type ChatMessage,
  type ThinkingState
} from '@/api/chat'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MoreFilled, ChatDotRound, User, Promotion, Loading } from '@element-plus/icons-vue'
// 消息正文渲染：转义 + 链接识别 + DOMPurify 净化
import { toSafeHtml } from '@/utils/rich-text'

const authStore = useAuthStore()

// 会话列表
const sessions = ref<SessionInfo[]>([])

// 当前会话
const currentSession = ref<SessionInfo | null>(null)

// 消息列表
const messages = ref<Array<ChatMessage & { completed?: boolean }>>([])

// 思考状态：null 表示空闲；否则显示"思考中/正在调用工具"的转圈提示
const thinkingState = ref<ThinkingState | null>(null)

// 思考提示文案（工具名映射成中文动作，未知工具回退为通用文案）
const thinkingText = computed(() => {
  const state = thinkingState.value
  if (!state) return ''

  if (state.stage === 'reasoning') {
    return '正在思考'
  }

  if (state.stage === 'tool' && state.tool) {
    const labels: Record<string, string> = {
      get_user_anime_history: '正在查询追番历史',
      get_user_watching_animes: '正在查询在看的番剧',
      get_user_completed_animes: '正在查询已完成的番剧',
      get_user_favorite_genres: '正在分析你的偏好类型',
      get_anime_info: '正在查询动漫详情',
      search_anime_by_name: '正在搜索动漫',
      get_user_watch_statistics: '正在统计观看数据',
      search_knowledge_base: '正在检索知识库'
    }
    // 去掉工具名前缀，仅用于兜底展示
    return labels[state.tool] || `正在调用 ${state.tool}`
  }

  return '正在思考'
})

// 输入消息
const inputMessage = ref('')

// 加载状态
const loading = ref(false)
const sending = ref(false)

// 重命名对话框
const renameDialogVisible = ref(false)
const newTitle = ref('')
const renamingSessionId = ref<string>('')

// 消息容器引用
const messagesContainer = ref<HTMLElement>()

// 会话计数器（用于生成自增编号）- 基于当前用户的会话数量
const sessionCounter = computed(() => {
  return sessions.value.length + 1
})

// 获取用户ID
const getUserId = () => {
  return authStore.userInfo?.id || 1
}

// 获取会话列表
const fetchSessions = async () => {
  try {
    const userId = getUserId()
    const response = await getSessions(userId)
    
    if (response.code === 200 && response.data) {
      sessions.value = response.data.sessions
    }
  } catch (error: any) {
    console.error('获取会话列表失败:', error)
  }
}

// 创建新会话
const handleCreateNewSession = async () => {
  try {
    const userId = getUserId()
    // 生成自增编号的会话名称（基于当前用户的会话数量）
    const sessionTitle = `新会话${sessionCounter.value}`
    
    const response = await createSession({ user_id: userId, title: sessionTitle })
    
    if (response.code === 200 && response.data) {
      // 先刷新会话列表
      await fetchSessions()
      
      // 等待DOM更新后再加载会话
      await nextTick()
      
      // 使用API返回的session_id直接加载
      const newSessionId = response.data.session_id
      if (newSessionId) {
        await loadSession(newSessionId)
      }
      
      ElMessage.success(`创建会话成功：${sessionTitle}`)
    }
  } catch (error: any) {
    console.error('创建会话失败:', error)
    ElMessage.error(error.message || '创建会话失败')
  }
}

// 加载会话消息
const loadSession = async (sessionId: string) => {
  loading.value = true
  try {
    const response = await getSessionMessages(sessionId)
    
    if (response.code === 200 && response.data) {
      // 设置当前会话（先设置，确保界面能响应）
      const session = sessions.value.find(s => s.session_id === sessionId)
      if (session) {
        currentSession.value = session
      }
      
      // 更新消息列表
      messages.value = response.data.messages.map(msg => ({
        ...msg,
        completed: true
      }))
      
      console.log('加载会话成功:', sessionId, '消息数量:', messages.value.length)
      
      // 滚动到底部
      await nextTick()
      scrollToBottom()
    } else {
      console.warn('获取消息失败:', response)
      // 即使没有消息也要设置当前会话
      const session = sessions.value.find(s => s.session_id === sessionId)
      if (session) {
        currentSession.value = session
        messages.value = []
      }
    }
  } catch (error: any) {
    console.error('加载消息失败:', error)
    ElMessage.error('加载消息失败')
  } finally {
    loading.value = false
  }
}

// 发送消息
const handleSend = async () => {
  const question = inputMessage.value.trim()
  
  if (!question || sending.value) {
    return
  }

  sending.value = true
  
  // 添加用户消息
  const userMessage: ChatMessage & { completed?: boolean } = {
    message_id: '',
    role: 'user',
    content: question,
    created_at: new Date().toISOString(),
    completed: true
  }
  messages.value.push(userMessage)
  
  // 清空输入
  inputMessage.value = ''
  
  // 滚动到底部
  await nextTick()
  scrollToBottom()

  // 添加AI回复占位符
  const aiMessageIndex = messages.value.length
  messages.value.push({
    message_id: '',
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString(),
    completed: false
  })

  let fullAnswer = ''

  try {
    // 调用流式接口
    await streamChat(
      question,
      getUserId(),
      currentSession.value?.session_id,
      // onChunk - 收到文本片段
      // 后端只过滤工具原始数据与 reasoning；过渡语（"我来查询一下"）也是正文
      (chunk) => {
        // 一旦开始出正文，思考提示就可以收起了
        thinkingState.value = null
        fullAnswer += chunk
        messages.value[aiMessageIndex].content = fullAnswer

        // 实时滚动
        scrollToBottom()
      },
      // onEnd - 传输完成
      (sessionId, messageId) => {
        thinkingState.value = null
        messages.value[aiMessageIndex].completed = true
        
        // 如果是新会话，更新当前会话
        if (sessionId && !currentSession.value) {
          fetchSessions()
          const session = sessions.value.find(s => s.session_id === sessionId)
          if (session) {
            currentSession.value = session
          }
        }
        
        sending.value = false
      },
      // onError - 错误处理
      (error, isAnimeRelated) => {
        thinkingState.value = null
        if (isAnimeRelated === false) {
          // 非动漫相关问题，显示友好提示
          messages.value[aiMessageIndex].content = error
          messages.value[aiMessageIndex].completed = true
        } else {
          // 系统错误
          ElMessage.error(error)
          messages.value.pop() // 移除失败的AI消息
        }
        sending.value = false
      },
      // onThinking - 思考 / reasoning / 工具调用中，显示转圈提示
      (state) => {
        thinkingState.value = state
        scrollToBottom()
      },
      // onRetract - 兼容保留：后端当前不再发出该事件
      () => {
        fullAnswer = ''
        messages.value[aiMessageIndex].content = ''
      }
    )
  } catch (error: any) {
    console.error('发送消息失败:', error)
    messages.value.pop() // 移除失败的AI消息
    sending.value = false
  }
}

// 处理会话命令
const handleSessionCommand = (command: string, sessionId: string) => {
  if (command === 'rename') {
    startRename(sessionId)
  } else if (command === 'delete') {
    confirmDelete(sessionId)
  }
}

// 开始重命名
const startRename = (sessionId: string) => {
  const session = sessions.value.find(s => s.session_id === sessionId)
  if (session) {
    renamingSessionId.value = sessionId
    newTitle.value = session.title
    renameDialogVisible.value = true
  }
}

// 确认重命名
const handleRenameConfirm = async () => {
  if (!newTitle.value.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }

  try {
    const response = await updateSessionTitle(renamingSessionId.value, {
      title: newTitle.value.trim()
    })
    
    if (response.code === 200) {
      ElMessage.success('重命名成功')
      renameDialogVisible.value = false
      await fetchSessions()
    }
  } catch (error: any) {
    ElMessage.error('重命名失败')
    console.error(error)
  }
}

// 确认删除
const confirmDelete = async (sessionId: string) => {
  try {
    await ElMessageBox.confirm('确定要删除这个会话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const response = await deleteSession(sessionId, false)
    
    if (response.code === 200) {
      ElMessage.success('删除成功')
      await fetchSessions()
      
      // 如果删除的是当前会话，清空消息
      if (currentSession.value?.session_id === sessionId) {
        currentSession.value = null
        messages.value = []
      }
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 监听消息变化，自动滚动
watch(
  () => messages.value.length,
  () => {
    nextTick(() => scrollToBottom())
  }
)

// 组件挂载时加载会话列表
onMounted(() => {
  // 确保用户已登录且有用户ID
  if (authStore.isLoggedIn && authStore.userInfo?.id) {
    fetchSessions()
  } else {
    console.warn('用户未登录或用户信息未加载')
  }
})
</script>

<style scoped lang="scss">
// 卡片背景不透明度（0.3 = 30% 不透明）。
//
// 用 rgba() 只让**背景**变半透明，而不是在容器上用 opacity：
// opacity 会作用于整棵子树，文字、头像、按钮都会一起变淡；rgba 背景则不影响内容。
// 调整时改这一个值即可。
$card-bg-alpha: 0.3;

.chat-view {
  // 锚定到 .layout-main（它已是 height: calc(100vh - 60px) 的定位父级），
  // 从而精确等于「主内容可视区」的高度。
  //
  // 为什么不用 height: 100vh 或 100%：
  //   - 100vh 比父级（100vh - 60px - 50px）高，会撑出 .layout-main 的滚动条，
  //     导致整张卡片被滚动，而不仅仅是消息列表；
  //   - 100% 也不行：父级 .main-content 只设了 min-height，没有确定高度，
  //     百分比高度无法解析。
  // 用 absolute 定位即可绕开这一层，且不污染 Layout 的全局样式。
  position: absolute;
  inset: 0;
  display: flex;

  .chat-container {
    display: flex;
    width: 100%;
    height: 100%;
    // 半透明背景（不用 opacity，避免文字一并变淡）
    background-color: rgba(255, 255, 255, $card-bg-alpha);
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  // 左侧会话列表
  .sidebar {
    width: 260px;
    flex-shrink: 0; // 侧边栏不压缩
    background-color: rgba(245, 247, 250, $card-bg-alpha);
    border-right: 1px solid #e0e0e0;
    display: flex;
    flex-direction: column;

    .sidebar-header {
      padding: 15px;
      border-bottom: 1px solid #e0e0e0;

      .el-button {
        width: 100%;
      }
    }

    .session-list {
      flex: 1;
      overflow-y: auto; // 会话列表可滚动
      overflow-x: hidden;
      padding: 10px;

      .session-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px;
        margin-bottom: 8px;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.3s ease;

        &:hover {
          background-color: #ecf5ff;
        }

        &.active {
          background-color: #409eff;
          color: #fff;

          .session-info {
            .el-icon {
              color: #fff;
            }
          }

          .session-more {
            color: #fff;
          }
        }

        .session-info {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 1;
          overflow: hidden;

          .el-icon {
            font-size: 18px;
            color: #409eff;
          }

          .session-title {
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 14px;
          }
        }

        .session-more {
          color: #909399;
          font-size: 16px;
          padding: 4px;
          border-radius: 4px;

          &:hover {
            background-color: rgba(0, 0, 0, 0.1);
          }
        }
      }
    }
  }

  // 右侧聊天区域
  .chat-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    // 背景交给内部的「对话背景」与输入区各自设置半透明，
    // 这里若留不透明白底会把底图挡回去
    min-height: 0; // 确保flex子元素可以正确滚动

    .messages-container {
      flex: 1; // 占据剩余空间
      overflow-y: auto; // 只有消息区域可以滚动
      overflow-x: hidden;
      padding: 20px;
      background-color: rgba(249, 250, 251, $card-bg-alpha);

      .welcome-message {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100%;
        text-align: center;
        color: #606266;

        .welcome-icon {
          font-size: 64px;
          margin-bottom: 20px;
        }

        h2 {
          font-size: 24px;
          color: #303133;
          margin-bottom: 15px;
        }

        p {
          font-size: 16px;
          margin-bottom: 10px;
        }

        ul {
          list-style: none;
          padding: 0;
          text-align: left;

          li {
            padding: 5px 0;
            font-size: 14px;
            color: #909399;

            &::before {
              content: '✓ ';
              color: #67c23a;
              font-weight: bold;
            }
          }
        }
      }

      .message {
        display: flex;
        gap: 12px;
        margin-bottom: 20px;
        animation: fadeIn 0.3s ease-in;

        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        &.user {
          flex-direction: row-reverse;

          .message-content {
            align-items: flex-end;

            .message-role {
              text-align: right;
            }

            .message-text {
              background-color: #409eff;
              color: #fff;

              // 蓝底气泡里的链接：用浅黄保证对比度，下划线表明可点
              :deep(a) {
                color: #ffe58f;
              }
            }
          }
        }

        .message-avatar {
          flex-shrink: 0;

          .ai-avatar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            font-size: 20px;
          }
        }

        .message-content {
          max-width: 70%;
          display: flex;
          flex-direction: column;
          gap: 6px;

          .message-role {
            font-size: 12px;
            color: #909399;
          }

          .message-text {
            padding: 12px 16px;
            border-radius: 12px;
            // 对话内容卡片保持不透明实色：半透明的是它背后的「对话背景」，
            // 文字压在底图上会看不清，所以这一层不要改成 rgba。
            background-color: #fff;
            color: #303133;
            line-height: 1.8; // 增加行高，更易阅读
            word-wrap: break-word;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
            
            // 段落样式
            :deep(p) {
              margin: 0 0 12px 0;
              
              &:last-child {
                margin-bottom: 0;
              }
            }

            // 链接样式：长 URL 允许断行，否则会撑破气泡
            :deep(a) {
              color: #409eff;
              text-decoration: underline;
              text-underline-offset: 2px;
              word-break: break-all;
              transition: color 0.2s ease;

              &:hover {
                color: #66b1ff;
              }
            }
          }

          .typing-indicator {
            display: inline-flex;
            gap: 4px;
            padding: 12px 16px;
            background-color: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);

            span {
              display: inline-block;
              width: 8px;
              height: 8px;
              border-radius: 50%;
              background-color: #409eff;
              animation: typing 1.4s infinite;

              &:nth-child(2) {
                animation-delay: 0.2s;
              }

              &:nth-child(3) {
                animation-delay: 0.4s;
              }
            }
          }

          /* 思考 / 工具调用提示（二次元风格） */
          .thinking-hint {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-top: 6px;
            padding: 8px 14px;
            border-radius: 12px;
            font-size: 0.85rem;
            color: #7c5cd6;
            background: linear-gradient(120deg, rgba(167, 139, 250, 0.18), rgba(236, 72, 153, 0.14));
            border: 1px solid rgba(139, 92, 246, 0.28);
            box-shadow: 0 2px 8px rgba(139, 92, 246, 0.12);
            animation: hint-fade-in 0.25s ease-out;

            .thinking-icon {
              font-size: 15px;
              color: #8b5cf6;
            }

            .thinking-text {
              display: inline-flex;
              align-items: baseline;
              gap: 2px;
              font-weight: 500;
            }

            /* 三个跳动的点 */
            .thinking-dots::after {
              content: '';
              animation: thinking-dots 1.4s steps(4, end) infinite;
            }
          }
        }
      }

      .loading-message {
        display: flex;
        justify-content: center;
        padding: 20px;

        .typing-indicator {
          display: flex;
          gap: 4px;

          span {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: #409eff;
            animation: typing 1.4s infinite;

            &:nth-child(2) {
              animation-delay: 0.2s;
            }

            &:nth-child(3) {
              animation-delay: 0.4s;
            }
          }
        }
      }
    }

    .input-area {
      flex-shrink: 0; // 输入区域不压缩
      padding: 20px;
      border-top: 1px solid #e0e0e0;
      background-color: rgba(255, 255, 255, $card-bg-alpha);

      .input-wrapper {
        display: flex;
        flex-direction: column;
        gap: 10px;

        .el-textarea {
          :deep(.el-textarea__inner) {
            border-radius: 8px;
            resize: none;
          }
        }

        .input-actions {
          display: flex;
          justify-content: space-between;
          align-items: center;

          .tip-text {
            font-size: 12px;
            color: #909399;
          }

          .el-button {
            min-width: 100px;
          }
        }
      }
    }
  }
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-10px);
  }
}

// 思考提示：淡入
@keyframes hint-fade-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

// 思考提示：省略号循环（. → .. → ... → 空）
@keyframes thinking-dots {
  0% { content: ''; }
  25% { content: '.'; }
  50% { content: '..'; }
  75% { content: '...'; }
  100% { content: ''; }
}

// 自定义滚动条样式
.messages-container,
.session-list {
  &::-webkit-scrollbar {
    width: 6px;
  }
  
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  
  &::-webkit-scrollbar-thumb {
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 3px;
    transition: background-color 0.3s ease;
    
    &:hover {
      background-color: rgba(0, 0, 0, 0.3);
    }
  }
}
</style>
