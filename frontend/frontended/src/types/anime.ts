// 动漫相关类型定义

// 动漫基本信息
export interface Anime {
  id: number
  title: string          // 中文标题
  coverImage: string     // 封面图URL
  episodes: number       // 总集数
  rating: number         // 评分
  watchStatus?: number   // 观看状态：0-未开始, 1-观看中, 2-已完成, 3-已放弃
}

// 分页响应数据
export interface PageResponse<T = any> {
  total: number          // 总数
  pages: number          // 总页数
  pageNum: number        // 当前页码
  pageSize: number       // 每页大小
  list: T[]              // 数据列表
}

// 动漫列表查询参数
export interface AnimeListQueryParams {
  pageNum: number            // 页码
  pageSize: number           // 每页数量
  title?: string             // 标题搜索关键词（可选）
  year?: number              // 年份筛选（可选）
}

// 动漫详情查询请求参数
export interface AnimeDetailQueryRequest {
  animeId: number            // 动漫ID
}

// 评论人信息（旧版，用于 aaaaa.vue 兼容）
export interface LegacyCommentUser {
  userId: number             // 用户ID
  username: string           // 用户名
  avatar: string             // 头像URL
}

// 评论回复信息（旧版，用于 aaaaa.vue 兼容）
export interface LegacyCommentReply {
  replyId: number            // 回复ID
  parentReplyId: number | null // 父回复ID（null表示直接回复主评论）
  content: string            // 回复内容
  createTime: string         // 创建时间
  replier: LegacyCommentUser // 回复人信息
  likeCount?: number         // 点赞数（可选）
  replies?: LegacyCommentReply[] // 子回复列表（支持多级嵌套）
  isLiked?: boolean          // 当前用户是否已点赞（可选）
}

// 评论信息（旧版，用于 aaaaa.vue 兼容）
export interface LegacyComment {
  commentId: number          // 评论ID
  userId: number             // 用户ID
  username: string           // 用户名
  avatar: string             // 头像URL
  content: string            // 评论内容
  likeCount: number          // 点赞数
  createTime: string         // 创建时间
  isLiked: boolean           // 当前用户是否已点赞
  replies?: LegacyCommentReply[] // 回复列表（可选）
}

// 发表评论请求参数
export interface AddCommentRequest {
  animeId: number            // 动漫ID
  content: string            // 评论内容
}

// 更新评论请求参数
export interface UpdateCommentRequest {
  commentId: number          // 评论ID
  content: string            // 评论内容
}

// 发表评论回复请求参数
export interface AddCommentReplyRequest {
  commentId: number          // 主评论ID
  parentReplyId?: number | null // 父回复ID（可选，null表示直接回复主评论）
  content: string            // 回复内容
}

// 用户点赞状态响应
export interface UserLikeStatusResponse {
  likedCommentIds: number[]  // 已点赞的评论ID集合
  likedReplyIds: number[]    // 已点赞的回复ID集合
}

// 当季新番基本信息（用于列表展示）
export interface SeasonalAnime {
  id: number                 // 动漫ID         
  title: string              // 标题
  coverImage: string         // 封面图URL
  rating: number             // 评分
  episodes: number           // 总集数
  status: number             // 状态：0-连载中, 1-已完结
  dayOfWeek: number | null   // 更新星期：1-周一, 2-周二, ..., 7-周日, null-待定
  updateTime?: string        // 更新时间（可选）
  mainId: number            // 主表ID（关联anime表的ID，必须）
}

// 轮播图信息
export interface BannerItem {
  animeId: number            // 动漫ID
  title: string              // 标题
  coverImage: string         // 封面图URL
  synopsis: string           // 简介
  rating: number             // 评分
  status?: number            // 状态：0-连载中, 1-已完结（可选）
  views?: number             // 观看次数（可选）
  genres?: string[]          // 题材标签（可选）
  mainId?: number            // 主表ID（关联anime表的ID，可选）
}

// 角色信息
export interface Character {
  id: number                 // 数据库角色ID
  malId: number              // MAL角色ID
  name: string               // 角色名称（英文/罗马音）
  nameJp: string             // 角色名称（日文）
  imageUrl: string           // 角色头像URL
  favorites: number          // 受欢迎程度（点赞数）
  isLiked?: number           // 用户是否喜欢该角色：0-未喜欢，1-喜欢（可选）
}

// 角色列表查询参数
export interface CharacterListQueryParams {
  pageNum: number            // 页码
  pageSize: number           // 每页数量
  name?: string              // 角色名称搜索关键词（可选）
}

// 角色详细信息
export interface CharacterDetail {
  id: number                 // 数据库角色ID
  malId: number              // MAL角色ID
  name: string               // 角色名称（英文/罗马音）
  nameJp: string             // 角色名称（日文）
  imageUrl: string           // 角色头像URL
  favorites: number          // 受欢迎程度（点赞数）
  about?: string             // 角色简介（可选）
  nicknames?: string         // 角色昵称/别名（逗号分隔，可选）
  birthday?: string          // 角色生日（MM-DD格式，可选）
}

// 角色评论人信息
export interface CharacterCommentUser {
  userId: number             // 用户ID
  avatar: string             // 头像URL
  nickname: string           // 昵称
}

// 角色评论回复信息
export interface CharacterCommentReply {
  replyId: number            // 回复ID
  parentReplyId: number | null // 父回复ID（null表示直接回复主评论）
  content: string            // 回复内容
  createdAt: string          // 回复时间
  replier: CharacterCommentUser // 回复人信息
  likeCount?: number         // 点赞数（可选）
  dislikeCount?: number      // 点踩数（可选）
  childReplies?: CharacterCommentReply[] // 子回复列表（支持多级嵌套）
  isLiked?: boolean          // 当前用户是否已点赞（可选）
}

// 角色评论信息
export interface CharacterComment {
  commentId: number          // 评论ID
  characterId: number        // 角色ID
  content: string            // 评论内容
  createdAt: string          // 评论时间
  commenter: CharacterCommentUser // 评论人信息
  likeCount?: number         // 点赞数（可选）
  dislikeCount?: number      // 点踩数（可选）
  replies?: CharacterCommentReply[] // 回复列表（可选）
  isLiked?: boolean          // 当前用户是否已点赞（可选）
}

// 角色详情响应数据
export interface CharacterDetailResponse {
  characterInfo: CharacterDetail // 角色信息
  comments: CharacterComment[]   // 评论列表
  isLiked: boolean               // 当前用户是否喜欢该角色
}

// 角色喜欢请求参数
export interface UserFavoriteCharacterRequest {
  characterId: number        // 角色ID
  favoriteStatus: number     // 喜欢状态：0-默认（未喜欢），1-喜欢
}

// 角色评论发表请求参数
export interface AddCharacterCommentRequest {
  characterId: number        // 角色ID
  content: string            // 评论内容
}

// 角色评论更新请求参数
export interface UpdateCharacterCommentRequest {
  commentId: number          // 评论ID
  content: string            // 评论内容
}

// 角色评论回复请求参数
export interface AddCharacterCommentReplyRequest {
  commentId: number          // 主评论ID
  parentReplyId?: number | null // 父回复ID（可选，null表示直接回复主评论）
  content: string            // 回复内容
}

// 角色评论点赞请求参数
export interface CharacterCommentLikeRequest {
  targetType: 'comment' | 'reply' // 目标类型：'comment' 或 'reply'
  targetId: number           // 目标ID（评论ID或回复ID）
  type: 'like' | 'dislike'   // 操作类型：'like' 或 'dislike'
}

// 用户角色评论点赞状态响应
export interface UserCharacterCommentLikeStatusResponse {
  likedCommentIds: number[]  // 已点赞的评论ID集合
  likedReplyIds: number[]    // 已点赞的回复ID集合
}







// ========== 动漫详情相关（匹配后端 AnimeDetailVO） ==========

/** 动漫详细信息（对应后端 AnimeDetailVO.AnimeInfo） */
export interface AnimeDetailInfo {
  id: number                   // 动漫ID
  title: string                // 标题（中文优先）
  coverImage: string           // 封面图URL
  synopsis: string             // 简介
  genres: string               // 题材/类型标签（逗号分隔字符串，API层转换为数组）
  releaseDate: string          // 发行时间
  rating: number               // 评分
  episodes: number             // 总集数
  status: number               // 状态: 0-连载中, 1-已完结
  watchStatus?: number         // 用户观看状态: 0-未开始, 1-观看中, 2-已完成, 3-已放弃
}

/** 动漫评论人信息（对应后端 AnimeDetailVO.UserInfo） */
export interface AnimeCommentUser {
  userId: number               // 用户ID
  avatar: string               // 头像URL
  nickname: string             // 昵称
}

/** 动漫评论回复 */
export interface AnimeCommentReply {
  replyId: number              // 回复ID
  parentReplyId: number | null // 父回复ID
  content: string              // 回复内容
  createdAt: string            // 回复时间
  replier: AnimeCommentUser    // 回复人信息
  likeCount?: number           // 点赞数
  isLiked?: boolean            // 当前用户是否已点赞
  replies?: AnimeCommentReply[] // 子回复列表（多级嵌套）
}

/** 动漫评论信息（对应后端 AnimeDetailVO.CommentWithUserInfo） */
export interface AnimeComment {
  commentId: number            // 评论ID
  content: string              // 评论内容
  createdAt: string            // 评论时间
  commenter: AnimeCommentUser  // 评论人信息
  likeCount?: number           // 点赞数（可选，由评论列表接口补充）
  replyCount?: number          // 回复总数（可选，由评论列表接口补充）
  isLiked?: boolean            // 当前用户是否已点赞（可选）
  replies?: AnimeCommentReply[] // 回复列表（可选，由评论列表接口补充）
}

/** 动漫详情响应（对应后端 AnimeDetailVO） */
export interface AnimeDetailResponse {
  animeInfo: AnimeDetailInfo     // 动画信息
  comments: AnimeComment[]       // 评论列表（包含评论人信息）
}

/** 兼容旧引用：CommentResponse = AnimeComment */
export type CommentResponse = AnimeComment
/** 兼容旧引用：CommentUser = AnimeCommentUser */
export type CommentUser = AnimeCommentUser
/** 兼容旧引用：CommentReply = AnimeCommentReply */
export type CommentReply = AnimeCommentReply

// ========== 更新观看状态 ==========

export interface UpdateWatchStatusRequest {
  animeId: number
  watchStatus: number        // 0-未开始, 1-观看中, 2-已完成, 3-已放弃
  currentEpisode?: number    // 当前观看集数
  rating?: undefined,    
  score?: number             // 评分（1-10）
  comment?: string           // 评论
  tags?: string              // 标签
}


