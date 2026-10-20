/**
 * 图片处理相关工具函数
 */

// 列表中使用的默认占位图（灰色底 + "动漫资讯"）
const NEWS_PLACEHOLDER = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmN2ZhIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxOCIgZmlsbD0iIzkwOTM5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPua8q+eUu+i1hOiurjwvdGV4dD48L3N2Zz4='

/**
 * 图片加载失败时替换为默认占位图
 * @param event - img 元素的 error 事件对象
 */
export const handleImageError = (event: Event): void => {
  const img = event.target as HTMLImageElement
  img.src = NEWS_PLACEHOLDER
}

/**
 * 获取默认占位图地址
 */
export const getDefaultImage = (): string => {
  return NEWS_PLACEHOLDER
}
