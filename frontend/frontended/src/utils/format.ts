/**
 * 时间与数字格式化工具函数
 */

/**
 * 格式化发布时间（统一为 YYYY-MM-DD HH:mm）
 * @param time - 时间字符串
 * @param fallback - 时间为空或非法时返回的文案
 */
export const formatDateTime = (time?: string, fallback: string = '时间待定'): string => {
  if (!time) return fallback

  const date = new Date(time)
  if (Number.isNaN(date.getTime())) return time

  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/**
 * 格式化数量（例如：15234 -> 1.5万）
 */
export const formatNumber = (num?: number): string => {
  if (!num || num < 0) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  return String(num)
}
