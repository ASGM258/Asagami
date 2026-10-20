import api from '@/utils/request'
import type { ApiResponse, AddCommentRequest, UpdateCommentRequest, AnimeComment, AddCommentReplyRequest, UserLikeStatusResponse } from '@/types'

/**
 * 发表评论
 */
export const addComment = (data: AddCommentRequest): Promise<ApiResponse<AnimeComment>> => {
  return api.post('/comment/add', data)
}

/**
 * 更新评论
 */
export const updateComment = (data: UpdateCommentRequest): Promise<ApiResponse<boolean>> => {
  return api.put('/comment/update', data)
}

/**
 * 删除评论
 */
export const deleteComment = (commentId: number): Promise<ApiResponse<boolean>> => {
  return api.delete(`/comment/delete/${commentId}`)
}

/**
 * 获取评论列表
 */
export const getCommentList = (animeId: number): Promise<ApiResponse<AnimeComment[]>> => {
  return api.get(`/comment/list/${animeId}`)
}

/**
 * 发表评论回复
 */
export const addCommentReply = (data: AddCommentReplyRequest): Promise<ApiResponse<any>> => {
  return api.post('/comment/reply/add', data)
}

/**
 * 删除评论回复
 */
export const deleteCommentReply = (replyId: number): Promise<ApiResponse<boolean>> => {
  return api.delete(`/comment/reply/delete/${replyId}`)
}

/**
 * 点赞/点踩（统一接口）
 * @param targetId - 目标ID（根评论ID或回复ID）
 * @param type - 'like' 表示点赞，'dislike' 表示取消点赞
 * @param targetType - 'comment' 表示根评论，'reply' 表示回复
 */
export const likeTarget = (targetId: number, type: 'like' | 'dislike', targetType: 'comment' | 'reply'): Promise<ApiResponse<any>> => {
  return api.post('/comment/like', { 
    targetId,            // 目标ID（根据targetType决定是commentId还是replyId）
    type,                // 'like' 或 'dislike'
    targetType           // 'comment' 或 'reply'
  })
}

/**
 * 获取用户点赞状态
 * @param animeId - 动漫ID
 */
export const getUserLikeStatus = (animeId: number): Promise<ApiResponse<UserLikeStatusResponse>> => {
  return api.get(`/comment/like/status/${animeId}`)
}
