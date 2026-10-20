/**
 * 富文本渲染：转义 → 识别链接 → DOMPurify 净化
 *
 * 为什么不能直接把模型输出塞进 v-html：
 * 模型的回答里会混入用户输入、知识库文档片段、B站视频标题等外部内容，
 * 一旦这些内容带上 `<img onerror=...>` 或 `javascript:` 链接，就是存储型 XSS。
 *
 * 因此这里的处理顺序是固定的：
 *   1. escapeHtml —— 先把所有 HTML 特殊字符转义，彻底断掉注入可能
 *   2. linkify     —— 只由我们插入 <a> 标签（href 必须是 http/https）
 *   3. DOMPurify   —— 兜底净化，只放行 p / br / a
 *
 * 第 1 步已经保证了「除了我们自己插入的标签，没有任何标签」，
 * DOMPurify 是第二道防线（纵深防御），而不是唯一防线。
 */

import DOMPurify from 'dompurify'

/** 只允许段落、换行与链接 */
const ALLOWED_TAGS = ['p', 'br', 'a']
/** 只允许链接必需属性 */
const ALLOWED_ATTR = ['href', 'target', 'rel']

/** 紧跟在链接后面的标点不应算进 href */
const TRAILING_PUNCTUATION = '.,;:!?)]}>，。；：！？）】」』》、…'

/** 匹配 http(s) 链接；排除空白与引号，避免把后续文字吞进来 */
const URL_PATTERN = /https?:\/\/[^\s<>"'`]+/g

const ESCAPE_MAP: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
}

/**
 * 转义 HTML 特殊字符
 *
 * 保留 `&` 转义是有意的：URL 里的 `&` 会变成 `&amp;`，
 * 浏览器解析 href 时会还原，语义不变。
 */
export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (char) => ESCAPE_MAP[char] ?? char)
}

/**
 * 只接受 http / https 绝对地址
 *
 * 显式挡掉 `javascript:`、`data:`、`vbscript:` 等危险协议。
 */
export function isSafeHttpUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

/** 拆掉链接末尾的句号、右括号等标点 */
export function splitTrailingPunctuation(raw: string): { url: string; tail: string } {
  let end = raw.length
  while (end > 0 && TRAILING_PUNCTUATION.includes(raw[end - 1])) {
    end -= 1
  }
  return { url: raw.slice(0, end), tail: raw.slice(end) }
}

/**
 * 把纯文本里的 URL 包成链接
 *
 * 入参必须是**已转义**的文本，否则可能把用户输入的属性拼进标签。
 */
export function linkify(escapedText: string): string {
  return escapedText.replace(URL_PATTERN, (raw) => {
    const { url, tail } = splitTrailingPunctuation(raw)
    if (!url || !isSafeHttpUrl(url)) {
      return raw
    }
    return (
      `<a href="${url}" target="_blank" rel="noopener noreferrer nofollow">${url}</a>` +
      tail
    )
  })
}

// 兜底：即使有标签绕过了前面的检查，也强制链接属性安全
let hookRegistered = false
function registerSanitizeHook(): void {
  if (hookRegistered || typeof DOMPurify.addHook !== 'function') {
    return
  }
  hookRegistered = true
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName !== 'A') {
      return
    }
    const href = node.getAttribute('href')
    if (!href || !isSafeHttpUrl(href)) {
      node.removeAttribute('href')
      return
    }
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer nofollow')
  })
}

/**
 * 是否可用 DOMPurify
 *
 * 无 DOM 环境（Node 脚本、SSR）里 dompurify 拿不到 window，此时不能调用 sanitize。
 * 这种情况下的降级是**安全的**：上文已经做过 HTML 转义，页面上只可能出现
 * 我们自己生成的 p / br / a，且 href 已通过 isSafeHttpUrl 校验。
 */
function canSanitize(): boolean {
  return typeof DOMPurify.sanitize === 'function'
}

/**
 * 结果缓存
 *
 * 流式输出时每个 token 都会重渲染整条消息，且 thinkingState 变化会让消息列表
 * 整体重渲染 —— 没有缓存的话同一段内容会被反复净化。缓存按内容做键，
 * 容量很小就够了（只有最近正在看的那几条会被重复渲染）。
 */
const CACHE_LIMIT = 50
const renderCache = new Map<string, string>()

/**
 * 把消息正文渲染为可安全 v-html 的 HTML
 *
 * 保留原有的排版习惯：单个换行用 <br>，空行分段用 <p>。
 *
 * @param content 原始纯文本（模型输出）
 * @returns 已净化的 HTML 字符串
 */
export function toSafeHtml(content: string): string {
  if (!content) {
    return ''
  }

  const cached = renderCache.get(content)
  if (cached !== undefined) {
    return cached
  }

  registerSanitizeHook()

  const escaped = escapeHtml(content)
  const withLinks = linkify(escaped)

  const html = withLinks
    .split(/\n{2,}/)
    .map((block) => block.replace(/\n/g, '<br>').trim())
    .filter((block) => block.length > 0)
    .map((block) => `<p>${block}</p>`)
    .join('')

  // 无 DOM 环境（Node 脚本、SSR）降级：此时 HTML 已由本模块转义并只含自造标签
  const safe = canSanitize()
    ? DOMPurify.sanitize(html, {
        ALLOWED_TAGS,
        ALLOWED_ATTR,
        ALLOW_DATA_ATTR: false,
        // 只放行 http(s) 地址，双保险
        ALLOWED_URI_REGEXP: /^https?:\/\//i
      })
    : html

  if (renderCache.size >= CACHE_LIMIT) {
    const oldest = renderCache.keys().next().value
    if (oldest !== undefined) {
      renderCache.delete(oldest)
    }
  }
  renderCache.set(content, safe)
  return safe
}
