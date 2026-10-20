package com.anime.manager.service;

import com.anime.manager.dto.CommentRequest;
import com.anime.manager.dto.CommentUpdateRequest;
import com.anime.manager.dto.CommentReplyRequest;
import com.anime.manager.vo.CommentResponse;

import java.util.List;

/**
 * 评论服务接口
 */
public interface CommentService {
    
    /**
     * 发表评论
     * 
     * @param request 评论请求（包含动漫ID和评论内容）
     * @return 评论响应（包含评论信息和评论人信息）
     */
    CommentResponse addComment(CommentRequest request);
    
    /**
     * 更新评论
     * 
     * @param request 更新请求（包含评论ID和新的评论内容）
     * @return 是否更新成功
     */
    boolean updateComment(CommentUpdateRequest request);
    
    /**
     * 删除评论
     * 
     * @param commentId 评论ID
     * @return 是否删除成功
     */
    boolean deleteComment(Long commentId);
    
    /**
     * 查询某动漫的所有评论（包含回复）
     * 
     * @param animeId 动漫ID
     * @return 评论列表（包含回复信息）
     */
    List<CommentResponse> getCommentsByAnimeId(Long animeId);
    
    /**
     * 发表评论回复
     * 
     * @param request 回复请求（包含主评论ID、父回复ID和回复内容）
     * @return 回复响应（包含回复信息和回复人信息）
     */
    com.anime.manager.vo.CommentReplyResponse addCommentReply(CommentReplyRequest request);
    
    /**
     * 删除评论回复
     * 
     * @param replyId 回复ID
     * @return 是否删除成功
     */
    boolean deleteCommentReply(Long replyId);
    
    /**
     * 点赞/取消点赞评论或回复
     * 
     * @param userId 用户ID
     * @param request 点赞请求（包含commentId/replyId、type、targetType）
     * @return 操作结果
     */
    boolean like(Long userId, com.anime.manager.dto.LikeRequest request);
    
    /**
     * 查询用户在某动漫下的点赞状态
     * 
     * @param userId 用户ID
     * @param animeId 动漫ID
     * @return 用户点赞状态（包含已点赞的评论ID和回复ID集合）
     */
    com.anime.manager.vo.UserLikeStatusResponse getUserLikeStatus(Long userId, Long animeId);
}
