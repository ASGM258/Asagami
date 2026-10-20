import api from '@/utils/request'
import type { ApiResponse, PageResponse, Anime, UpdateWatchStatusRequest, AnimeListQueryParams, AnimeDetailResponse, AnimeDetailQueryRequest, SeasonalAnime, BannerItem, Character, CharacterListQueryParams, CharacterDetailResponse, UserFavoriteCharacterRequest, AddCharacterCommentRequest, UpdateCharacterCommentRequest, AddCharacterCommentReplyRequest, CharacterCommentLikeRequest, UserCharacterCommentLikeStatusResponse, AddCommentRequest, UpdateCommentRequest, AddCommentReplyRequest } from '@/types'

/**
 * 获取动漫列表（分页）
 */
export const getAnimeList = (params: AnimeListQueryParams): Promise<ApiResponse<PageResponse<Anime>>> => {
  return api.get('/anime/list', { params })
}

/**
 * 获取动漫详情（包含评论）
 * 参考 getCharacterDetail 的模式，支持直接传入 animeId 或请求对象
 */
export const getAnimeDetail = (animeIdOrRequest: number | AnimeDetailQueryRequest): Promise<ApiResponse<AnimeDetailResponse>> => {
  const animeId = typeof animeIdOrRequest === 'number' ? animeIdOrRequest : animeIdOrRequest.animeId
  return api.post('/anime/detail', { animeId }).then((response: any) => {
    // 后端 genres 返回逗号分隔字符串，前端转换为数组供 v-for 使用
    if (response.data?.animeInfo?.genres && typeof response.data.animeInfo.genres === 'string') {
      response.data.animeInfo.genres = (response.data.animeInfo.genres as string).split(',').map((g: string) => g.trim()).filter(Boolean) as any
    }
    return response
  })
}

/**
 * 更新追番状态
 */
export const updateWatchStatus = (data: UpdateWatchStatusRequest): Promise<ApiResponse<boolean>> => {
  return api.post('/anime/user-anime/update', data)
}

/**
 * 获取观看历史列表（分页）
 */
export const getWatchHistoryList = (params: AnimeListQueryParams): Promise<ApiResponse<PageResponse<Anime>>> => {
  return api.get('/anime/watch-history', { params })
}

/**
 * 获取轮播图数据
 */
export const getBanners = (): Promise<ApiResponse<BannerItem[]>> => {
  return api.get('/anime/banners')
}

/**
 * 获取当季新番列表（按星期分类）
 * @param dayOfWeek - 星期几：1-7对应周一到周日，8表示待定（dayOfWeek为null），不传则返回所有
 */
export const getSeasonalAnime = (dayOfWeek?: number): Promise<ApiResponse<SeasonalAnime[]>> => {
  const params = dayOfWeek ? { dayOfWeek } : {}
  return api.get('/anime/seasonal', { params })
}

/**
 * 根据main_id查找anime表的ID
 * @param mainId - 主表ID
 * @returns anime表的ID，如果不存在则返回null
 */
export const getAnimeIdByMainId = (mainId: number): Promise<ApiResponse<number | null>> => {
  return api.get(`/anime/id-by-main/${mainId}`)
}

/**
 * 刷新当季新番数据（爬虫抓取）
 * @returns 刷新结果消息
 */
export const refreshSeasonalAnime = (): Promise<ApiResponse<string>> => {
  return api.post('/anime/scraper/seasonal/refresh')
}

/**
 * 获取角色列表（分页）
 */
export const getCharacterList = (params: CharacterListQueryParams): Promise<ApiResponse<PageResponse<Character>>> => {
  return api.get('/character/list', { params })
}

/**
 * 获取角色详情
 */
export const getCharacterDetail = (characterId: number): Promise<ApiResponse<CharacterDetailResponse>> => {
  return api.post('/character/detail', { characterId })
}

/**
 * 更新或创建角色喜欢记录
 */
export const updateCharacterFavorite = (data: UserFavoriteCharacterRequest): Promise<ApiResponse<boolean>> => {
  return api.post('/character/favorite/update', data)
}

/**
 * 发表角色评论
 */
export const addCharacterComment = (characterId: number, content: string): Promise<ApiResponse<any>> => {
  return api.post(`/character/comment/add/${characterId}`, content)
}

/**
 * 更新角色评论
 */
export const updateCharacterComment = (commentId: number, content: string): Promise<ApiResponse<boolean>> => {
  return api.put(`/character/comment/update/${commentId}`, content)
}

/**
 * 删除角色评论
 */
export const deleteCharacterComment = (commentId: number): Promise<ApiResponse<boolean>> => {
  return api.delete(`/character/comment/delete/${commentId}`)
}

/**
 * 获取角色评论列表
 */
export const getCharacterCommentList = (characterId: number): Promise<ApiResponse<any[]>> => {
  return api.get(`/character/comment/list/${characterId}`)
}

/**
 * 发表角色评论回复
 */
export const addCharacterCommentReply = (data: AddCharacterCommentReplyRequest): Promise<ApiResponse<any>> => {
  return api.post('/character/comment/reply/add', data)
}

/**
 * 删除角色评论回复
 */
export const deleteCharacterCommentReply = (replyId: number): Promise<ApiResponse<boolean>> => {
  return api.delete(`/character/comment/reply/delete/${replyId}`)
}

/**
 * 点赞/取消点赞角色评论或回复
 */
export const likeCharacterComment = (data: CharacterCommentLikeRequest): Promise<ApiResponse<boolean>> => {
  return api.post('/character/comment/like', data)
}

/**
 * 获取用户角色评论点赞状态
 */
export const getUserCharacterCommentLikeStatus = (characterId: number): Promise<ApiResponse<UserCharacterCommentLikeStatusResponse>> => {
  return api.get(`/character/comment/like/status/${characterId}`)
}

/**
 * 获取喜欢的角色列表（分页）
 */
export const getFavoriteCharacterList = (params: CharacterListQueryParams): Promise<ApiResponse<PageResponse<Character>>> => {
  return api.get('/character/favorite/history', { params })
}

/**
 * 发表动漫评论
 */
export const addAnimeComment = (data: AddCommentRequest): Promise<ApiResponse<any>> => {
  return api.post(`/anime/comment/add/${data.animeId}`, data.content)
}

/**
 * 更新动漫评论
 */
export const updateAnimeComment = (commentId: number, content: string): Promise<ApiResponse<boolean>> => {
  return api.put(`/anime/comment/update/${commentId}`, content)
}

/**
 * 删除动漫评论
 */
export const deleteAnimeComment = (commentId: number): Promise<ApiResponse<boolean>> => {
  return api.delete(`/anime/comment/delete/${commentId}`)
}

/**
 * 发表动漫评论回复
 */
export const addAnimeCommentReply = (data: AddCommentReplyRequest): Promise<ApiResponse<any>> => {
  return api.post('/anime/comment/reply/add', data)
}

/**
 * 删除动漫评论回复
 */
export const deleteAnimeCommentReply = (replyId: number): Promise<ApiResponse<boolean>> => {
  return api.delete(`/anime/comment/reply/delete/${replyId}`)
}

/**
 * 清除所有缓存（管理员功能）
 * @returns 清除结果，包含删除的key数量
 */
export const clearAllCache = (): Promise<ApiResponse<{ deletedCount: number }>> => {
  return api.post('/admin/cache/clear-all')
}
