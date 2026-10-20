/**
 * 消息富文本渲染的自检脚本
 *
 * 运行：npm run test:rich-text
 * 用 jsdom 造一个真 DOM，让 DOMPurify 真正生效，验证：
 * 1. HTML 转义（XSS 第一道防线）
 * 2. URL → 可点击链接（含末尾标点、危险协议）
 * 3. DOMPurify 净化（第二道防线）
 * 4. 排版：单换行 <br>、空行 <p>
 */
import { JSDOM } from 'jsdom'

// 必须先造好全局 DOM，再动态导入被测模块：
// dompurify 在模块加载时就会从全局 window 创建实例
const dom = new JSDOM('<!doctype html><html><body></body></html>')
const globalAny = globalThis as Record<string, unknown>
globalAny.window = dom.window
globalAny.document = dom.window.document

const mod = await import('../src/utils/rich-text.ts')
const { escapeHtml, isSafeHttpUrl, linkify, splitTrailingPunctuation, toSafeHtml } = mod

let passed = 0
let failed = 0

function check(name: string, actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) === JSON.stringify(expected)) {
    passed += 1
    console.log(`  ok   ${name}`)
  } else {
    failed += 1
    console.log(
      `  FAIL ${name}\n    actual  : ${JSON.stringify(actual)}\n    expected: ${JSON.stringify(expected)}`
    )
  }
}

function checkContains(name: string, haystack: string, needle: string): void {
  if (haystack.includes(needle)) {
    passed += 1
    console.log(`  ok   ${name}`)
  } else {
    failed += 1
    console.log(`  FAIL ${name}\n    actual: ${haystack}`)
  }
}

function checkNotContains(name: string, haystack: string, needle: string): void {
  if (!haystack.includes(needle)) {
    passed += 1
    console.log(`  ok   ${name}`)
  } else {
    failed += 1
    console.log(`  FAIL ${name}\n    actual: ${haystack}`)
  }
}

console.log('== escapeHtml ==')
check('转义尖括号', escapeHtml('<b>x</b>'), '&lt;b&gt;x&lt;/b&gt;')
check('转义引号', escapeHtml('a"b\'c'), 'a&quot;b&#39;c')
check('转义 &', escapeHtml('a&b'), 'a&amp;b')

console.log('== isSafeHttpUrl ==')
check('https 通过', isSafeHttpUrl('https://www.bilibili.com/video/BV1'), true)
check('http 通过', isSafeHttpUrl('http://example.com'), true)
check('javascript 拒绝', isSafeHttpUrl('javascript:alert(1)'), false)
check('data 拒绝', isSafeHttpUrl('data:text/html,<script>'), false)
check('相对地址拒绝', isSafeHttpUrl('/video/BV1'), false)

console.log('== 末尾标点拆分 ==')
check('中文句号', splitTrailingPunctuation('https://b23.tv/abc。'), {
  url: 'https://b23.tv/abc',
  tail: '。'
})
check('英文句号', splitTrailingPunctuation('https://x.com/a.'), {
  url: 'https://x.com/a',
  tail: '.'
})
check('右括号', splitTrailingPunctuation('https://x.com/a)'), {
  url: 'https://x.com/a',
  tail: ')'
})

console.log('== linkify（入参已转义）==')
const linked = linkify('看这个 https://www.bilibili.com/video/BV1Pa411F7xw 不错')
checkContains('生成 a 标签', linked, '<a href="https://www.bilibili.com/video/BV1Pa411F7xw"')
checkContains('带 target', linked, 'target="_blank"')
checkContains('带 rel', linked, 'rel="noopener noreferrer nofollow"')
checkContains('链接文字保留', linked, '>https://www.bilibili.com/video/BV1Pa411F7xw</a>')

const pmid = linkify('见 https://b23.tv/abc。')
checkContains('标点留在链接外', pmid, '</a>。')
checkNotContains('标点不进 href', pmid, 'abc。</a>')

console.log('== toSafeHtml：XSS 防护 ==')
const injected = toSafeHtml('<img src=x onerror="alert(1)">以及<script>alert(2)</script>')
checkNotContains('没有 img 标签', injected, '<img')
checkNotContains('没有 script 标签', injected, '<script')
checkContains('原文被转义展示', injected, '&lt;img')

const jsLink = toSafeHtml('点我 javascript:alert(1) 这里')
checkNotContains('javascript 不成链接', jsLink, '<a')

// DOMPurify 真实生效：构造一段「能绕过手写检查」的 HTML 直接喂给 sanitize，
// 确认净化器本身会砍掉危险标签与危险属性
const domPurify = (await import('dompurify')).default
const dirty =
  '<p>安全文本</p><a href="javascript:alert(1)">x</a>' +
  '<iframe src="https://evil.test"></iframe><img src=x onerror=alert(1)>' +
  '<p onclick="alert(2)">点击</p>'
const clean = domPurify.sanitize(dirty, {
  ALLOWED_TAGS: ['p', 'br', 'a'],
  ALLOWED_ATTR: ['href', 'target', 'rel'],
  ALLOW_DATA_ATTR: false,
  ALLOWED_URI_REGEXP: /^https?:\/\//i
})
checkNotContains('净化掉 iframe', clean, '<iframe')
checkNotContains('净化掉 img', clean, '<img')
checkNotContains('净化掉 onclick', clean, 'onclick')
checkNotContains('净化掉 javascript 协议', clean, 'javascript:')
checkContains('保留安全段落', clean, '安全文本')

console.log('== toSafeHtml：排版 ==')
check('空字符串', toSafeHtml(''), '')
check('单段落', toSafeHtml('一行'), '<p>一行</p>')
check('单换行变 br', toSafeHtml('第一行\n第二行'), '<p>第一行<br>第二行</p>')
check('空行分段', toSafeHtml('第一段\n\n第二段'), '<p>第一段</p><p>第二段</p>')
check('多余空行忽略', toSafeHtml('a\n\n\n\nb'), '<p>a</p><p>b</p>')

console.log('== 缓存 ==')
const cachedInput = '缓存测试 https://b23.tv/x'
const firstRun = toSafeHtml(cachedInput)
const secondRun = toSafeHtml(cachedInput)
check('重复渲染结果一致', secondRun, firstRun)
checkContains('缓存后仍是链接', secondRun, '<a href="https://b23.tv/x"')

console.log('== toSafeHtml：真实 B 站回答片段 ==')
const answer = `以下是《斩服少女》相关的 B 站视频推荐：

1. 斩服少女 有后续故事？
   https://www.bilibili.com/video/BV1Pa411F7xw

2. 这女主....太会了吧!!!
   https://www.bilibili.com/video/BV1Dt4y1x7fb`
const rendered = toSafeHtml(answer)
check('两条链接都被识别', (rendered.match(/<a /g) || []).length, 2)
checkContains('保留列表文本', rendered, '斩服少女 有后续故事？')
checkContains('链接指向 B 站', rendered, 'href="https://www.bilibili.com/video/BV1Dt4y1x7fb"')
checkNotContains('没有残留 div 标签', rendered, '<div')

console.log(`\n结果: ${passed} passed, ${failed} failed`)
if (failed > 0) {
  process.exit(1)
}
