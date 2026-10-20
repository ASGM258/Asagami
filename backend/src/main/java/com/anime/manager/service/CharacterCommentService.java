package com.anime.manager.service;

import com.anime.manager.dto.CommentReplyRequest;
import com.anime.manager.dto.LikeRequest;
import com.anime.manager.vo.CharacterCommentResponse;
import com.anime.manager.vo.CommentReplyResponse;
import com.anime.manager.vo.UserLikeStatusResponse;

import java.util.List;

/**
 * 角色评论服务接口
 */
public interface CharacterCommentService {
    
    /**
     * 发表评论
     * @param characterId 角色ID
     * @param content 评论内容
     * @return 评论响应
     */
    CharacterCommentResponse addComment(Long characterId, String content);
    
    /**
     * 更新评论
     * @param commentId 评论ID
     * @param content 新的评论内容
     * @return 是否成功
     */
    boolean updateComment(Long commentId, String content);
    
    /**
     * 删除评论
     * @param commentId 评论ID
     * @return 是否成功
     */
    boolean deleteComment(Long commentId);
    
    /**
     * 查询某角色的所有评论
     * @param characterId 角色ID
     * @return 评论列表（包含回复）
     */
    List<CharacterCommentResponse> getCommentsByCharacterId(Long characterId);
    
    /**
     * 发表评论回复
     * @param request 回复请求
     * @return 回复响应
     */
    CommentReplyResponse addCommentReply(CommentReplyRequest request);
    
    /**
     * 删除评论回复
     * @param replyId 回复ID
     * @return 是否成功
     */
    boolean deleteCommentReply(Long replyId);
    
    /**
     * 点赞/取消点赞评论或回复
     * @param userId 用户ID
     * @param request 点赞请求
     * @return 是否成功
     */
    boolean like(Long userId, LikeRequest request);
    
    /**
     * 查询用户在某角色下的点赞状态
     * @param userId 用户ID
     * @param characterId 角色ID
     * @return 用户点赞状态
     */
    UserLikeStatusResponse getUserLikeStatus(Long userId, Long characterId);
}
