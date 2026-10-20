// 动漫资讯相关类型定义

// 资讯列表项（对应列表接口返回的每一条）
export interface NewsItem {
  id: number                 // 资讯ID
  title: string              // 标题
  coverImage: string         // 缩略图URL
  summary?: string           // 摘要（列表右侧展示的简短描述）
  category?: string          // 分类：动画 / 漫画 / 声优 / 游戏 / 活动 等
  source?: string            // 来源（如：再漫画）
  author?: string            // 发布者（如：苦力A）
  publishTime?: string       // 发布时间
  tags?: string[]            // 标签（如：['预告影像', '原创动画电影']）
  viewCount?: number         // 阅读量（可选）
}

// 资讯详情（列表项 + 正文）
export interface NewsDetail extends NewsItem {
  content: string            // 正文（后端返回HTML或纯文本）
  relatedAnimeId?: number    // 关联动漫ID（可选，用于跳转到动漫详情）
  relatedAnimeTitle?: string // 关联动漫标题（可选）
}

// 资讯列表查询参数
export interface NewsListQueryParams {
  pageNum: number            // 页码（从1开始）
  pageSize: number           // 每页数量
  category?: string          // 分类筛选（可选，'all' 或空表示全部）
  keyword?: string           // 关键词搜索（可选）
}

// 资讯详情查询请求参数
export interface NewsDetailQueryRequest {
  newsId: number             // 资讯ID
}

// 资讯分类项（用于顶部筛选标签）
export interface NewsCategory {
  key: string                // 分类标识（如：'animation'）
  name: string               // 分类名称（如：'动画'）
  count?: number             // 该分类下的资讯数量（可选）
}
