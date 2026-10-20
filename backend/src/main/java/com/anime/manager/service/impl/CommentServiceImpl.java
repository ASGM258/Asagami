package com.anime.manager.service.impl;

import com.anime.manager.common.CacheKeyConstants;
import com.anime.manager.common.UserContext;
import com.anime.manager.dto.CommentRequest;
import com.anime.manager.dto.CommentUpdateRequest;
import com.anime.manager.dto.CommentReplyRequest;
import com.anime.manager.dto.LikeRequest;
import com.anime.manager.entity.Comment;
import com.anime.manager.entity.CommentReply;
import com.anime.manager.entity.User;
import com.anime.manager.entity.UserCommentLike;
import com.anime.manager.mapper.CommentMapper;
import com.anime.manager.mapper.CommentReplyMapper;
import com.anime.manager.mapper.UserCommentLikeMapper;
import com.anime.manager.mapper.UserMapper;
import com.anime.manager.service.CacheService;
import com.anime.manager.service.CommentService;
import com.anime.manager.vo.CommentResponse;
import com.anime.manager.vo.CommentReplyResponse;
import com.anime.manager.vo.UserLikeStatusResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * 评论服务实现类
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CommentServiceImpl implements CommentService {
    
    private final CommentMapper commentMapper;
    private final CommentReplyMapper commentReplyMapper;
    private final UserCommentLikeMapper userCommentLikeMapper;
    private final UserMapper userMapper;
    private final CacheService cacheService;
    
    /**
     * 发表评论
     */
    @Override
    public CommentResponse addComment(CommentRequest request) {
        log.info("发表评论: animeId={}, content={}", request.getAnimeId(), request.getContent());
        
        // 获取当前登录用户ID
        Long userId = UserContext.getUserId();
        if (userId == null) {
            throw new RuntimeException("请先登录");
        }
        
        // 验证评论内容
        if (request.getContent() == null || request.getContent().trim().isEmpty()) {
            throw new IllegalArgumentException("评论内容不能为空");
        }
        
        // 创建评论对象
        Comment comment = Comment.builder()
            .animeId(request.getAnimeId())
            .userId(userId)
            .content(request.getContent())
            .build();
        
        // 插入评论
        int result = commentMapper.insert(comment);
        if (result <= 0) {
            throw new RuntimeException("发表评论失败");
        }
        
        // 查询评论人信息
        User commenter = userMapper.findById(userId);
        
        // 构建响应
        CommentResponse.CommenterInfo commenterInfo = CommentResponse.CommenterInfo.builder()
            .userId(commenter != null ? commenter.getId() : null)
            .avatar(commenter != null ? commenter.getAvatar() : null)
            .nickname(commenter != null ? commenter.getNickname() : "未知用户")
            .build();
        
        CommentResponse response = CommentResponse.builder()
            .commentId(comment.getId())
            .animeId(comment.getAnimeId())
            .content(comment.getContent())
            .likeCount(comment.getLikeCount())
            .dislikeCount(comment.getDislikeCount())
            .createdAt(comment.getCreatedAt())
            .commenter(commenterInfo)
            .replies(buildReplies(comment.getId()))
            .build();
        
        log.info("评论发表成功: commentId={}", comment.getId());
        
        // 清除相关缓存
        clearCommentCache(comment.getAnimeId(), comment.getId());
        
        return response;
    }
    
    /**
     * 更新评论
     */
    @Override
    public boolean updateComment(CommentUpdateRequest request) {
        log.info("更新评论: commentId={}", request.getCommentId());
        
        // 获取当前登录用户ID
        Long userId = UserContext.getUserId();
        if (userId == null) {
            throw new RuntimeException("请先登录");
        }
        
        // 查询评论是否存在
        Comment comment = commentMapper.findById(request.getCommentId());
        if (comment == null) {
            throw new RuntimeException("评论不存在4444444444444444444");
        }
        
        // 验证权限：只能修改自己的评论
        if (!comment.getUserId().equals(userId)) {
            throw new RuntimeException("无权修改他人的评论");
        }
        
        // 更新评论
        int result = commentMapper.updateContent(request.getCommentId(), request.getContent());
        
        log.info("评论更新完成: result={}", result > 0);
        
        // 清除相关缓存（使用之前查询的comment对象）
        clearCommentCache(comment.getAnimeId(), comment.getId());
        
        return result > 0;
    }
    
    /**
     * 删除评论
     */
    @Override
    public boolean deleteComment(Long commentId) {
        log.info("删除评论: commentId={}", commentId);
        
        // 获取当前登录用户ID
        Long userId = UserContext.getUserId();
        if (userId == null) {
            throw new RuntimeException("请先登录");
        }
        
        // 查询评论是否存在
        Comment comment = commentMapper.findById(commentId);
        if (comment == null) {
            throw new RuntimeException("评论不存在");
        }
        
        // 验证权限：只能删除自己的评论
        if (!comment.getUserId().equals(userId)) {
            throw new RuntimeException("无权删除他人的评论");
        }
        
        // 删除评论
        int result = commentMapper.deleteById(commentId);
        
        log.info("评论删除完成: result={}", result > 0);
        
        // 清除相关缓存
        clearCommentCache(comment.getAnimeId(), commentId);
        
        return result > 0;
    }
    
    /**
     * 查询某动漫的所有评论
     */
    @Override
    public List<CommentResponse> getCommentsByAnimeId(Long animeId) {
        log.info("查询动漫评论: animeId={}", animeId);
        
        if (animeId == null) {
            throw new IllegalArgumentException("动漫ID不能为空");
        }
        
        // 生成缓存键
        String cacheKey = String.format(CacheKeyConstants.COMMENT_ANIME, animeId);
        
        // 尝试从缓存获取
        @SuppressWarnings("unchecked")
        List<CommentResponse> cachedResult = cacheService.get(cacheKey);
        if (cachedResult != null) {
            log.info("从缓存获取评论列表: key={}", cacheKey);
            return cachedResult;
        }
        
        // 缓存未命中，查询数据库
        log.info("缓存未命中，查询数据库");
        
        // 查询评论列表
        List<Comment> comments = commentMapper.findByAnimeId(animeId);
        
        // 组装响应数据
        List<CommentResponse> responses = comments.stream()
            .map(comment -> {
                // 查询评论人信息
                User commenter = userMapper.findById(comment.getUserId());
                
                // 构建用户信息
                CommentResponse.CommenterInfo commenterInfo = CommentResponse.CommenterInfo.builder()
                    .userId(commenter != null ? commenter.getId() : null)
                    .avatar(commenter != null ? commenter.getAvatar() : null)
                    .nickname(commenter != null ? commenter.getNickname() : "未知用户")
                    .build();
                
                // 构建评论响应
                return CommentResponse.builder()
                    .commentId(comment.getId())
                    .animeId(comment.getAnimeId())
                    .content(comment.getContent())
                    .likeCount(comment.getLikeCount())
                    .dislikeCount(comment.getDislikeCount())
                    .createdAt(comment.getCreatedAt())
                    .commenter(commenterInfo)
                    .replies(buildReplies(comment.getId()))
                    .build();
            })
            .toList();
        
        log.info("查询完成: 评论数量={}", responses.size());
        
        // 将结果存入缓存，过期时间30分钟
        cacheService.set(cacheKey, responses, 30, TimeUnit.MINUTES);
        log.info("数据已存入缓存: key={}", cacheKey);
        
        return responses;
    }
    
    /**
     * 发表评论回复
     */
    @Override
    public CommentReplyResponse addCommentReply(CommentReplyRequest request) {
        log.info("发表评论回复: commentId={}, parentReplyId={}", request.getCommentId(), request.getParentReplyId());
        
        // 获取当前登录用户ID
        Long userId = UserContext.getUserId();
        if (userId == null) {
            throw new RuntimeException("请先登录");
        }
        
        // 验证评论内容
        if (request.getContent() == null || request.getContent().trim().isEmpty()) {
            throw new IllegalArgumentException("回复内容不能为空");
        }
        
        // 创建回复对象
        CommentReply reply = CommentReply.builder()
            .commentId(request.getCommentId())
            .userId(userId)
            .parentReplyId(request.getParentReplyId())
            .content(request.getContent())
            .build();
        
        // 插入回复
        int result = commentReplyMapper.insert(reply);
        if (result <= 0) {
            throw new RuntimeException("发表回复失败");
        }
        
        // 查询回复人信息
        User replier = userMapper.findById(userId);
        
        // 构建响应
        CommentReplyResponse.ReplyUserInfo replierInfo = CommentReplyResponse.ReplyUserInfo.builder()
            .userId(replier != null ? replier.getId() : null)
            .avatar(replier != null ? replier.getAvatar() : null)
            .nickname(replier != null ? replier.getNickname() : "未知用户")
            .build();
        
        CommentReplyResponse response = CommentReplyResponse.builder()
            .replyId(reply.getId())
            .parentReplyId(reply.getParentReplyId())
            .content(reply.getContent())
            .likeCount(reply.getLikeCount())
            .dislikeCount(reply.getDislikeCount())
            .createdAt(reply.getCreatedAt())
            .replier(replierInfo)
            .childReplies(null)
            .build();
        
        log.info("回复发表成功: replyId={}", reply.getId());
        
        // 清除相关缓存
        Comment comment = commentMapper.findById(request.getCommentId());
        if (comment != null) {
            clearCommentCache(comment.getAnimeId(), request.getCommentId());
        }
        
        return response;
    }
    
    /**
     * 删除评论回复
     */
    @Override
    public boolean deleteCommentReply(Long replyId) {
        log.info("删除评论回复: replyId={}", replyId);
        
        // 获取当前登录用户ID
        Long userId = UserContext.getUserId();
        if (userId == null) {
            throw new RuntimeException("请先登录");
        }
        
        // 查询回复是否存在
        CommentReply reply = commentReplyMapper.findById(replyId);
        if (reply == null) {
            throw new RuntimeException("回复不存在");
        }
        
        // 验证权限：只能删除自己的回复
        if (!reply.getUserId().equals(userId)) {
            throw new RuntimeException("无权删除他人的回复");
        }
        
        // 删除回复
        int result = commentReplyMapper.deleteById(replyId);
        
        // 同时删除所有子回复
        commentReplyMapper.deleteByParentReplyId(replyId);
        
        log.info("回复删除完成: result={}", result > 0);
        
        // 清除相关缓存
        Comment comment = commentMapper.findById(reply.getCommentId());
        if (comment != null) {
            clearCommentCache(comment.getAnimeId(), reply.getCommentId());
        }
        
        return result > 0;
    }
    
    /**
     * 构建回复树（递归）
     */
    private List<CommentReplyResponse> buildReplies(Long commentId) {
        List<CommentReply> replies = commentReplyMapper.findByCommentId(commentId);
        if (replies == null || replies.isEmpty()) {
            return null;
        }
        
        // 只返回顶级回复（parentReplyId为NULL的）
        List<CommentReply> topLevelReplies = replies.stream()
            .filter(r -> r.getParentReplyId() == null)
            .toList();
        
        return topLevelReplies.stream()
            .map(reply -> buildReplyTree(reply, replies))
            .toList();
    }
    
    /**
     * 递归构建回复树
     */
    private CommentReplyResponse buildReplyTree(CommentReply reply, List<CommentReply> allReplies) {
        // 查询回复人信息
        User replier = userMapper.findById(reply.getUserId());
        
        // 构建用户信息
        CommentReplyResponse.ReplyUserInfo replierInfo = CommentReplyResponse.ReplyUserInfo.builder()
            .userId(replier != null ? replier.getId() : null)
            .avatar(replier != null ? replier.getAvatar() : null)
            .nickname(replier != null ? replier.getNickname() : "未知用户")
            .build();
        
        // 查找子回复
        List<CommentReply> childReplies = allReplies.stream()
            .filter(r -> reply.getId().equals(r.getParentReplyId()))
            .toList();
        
        // 递归构建子回复
        List<CommentReplyResponse> childResponses = childReplies.stream()
            .map(child -> buildReplyTree(child, allReplies))
            .toList();
        
        // 构建回复响应
        return CommentReplyResponse.builder()
            .replyId(reply.getId())
            .parentReplyId(reply.getParentReplyId())
            .content(reply.getContent())
            .likeCount(reply.getLikeCount())
            .dislikeCount(reply.getDislikeCount())
            .createdAt(reply.getCreatedAt())
            .replier(replierInfo)
            .childReplies(childResponses.isEmpty() ? null : childResponses)
            .build();
    }
    
    /**
     * 处理评论点赞
     */
    private boolean handleCommentLike(Long userId, Long commentId, String type) {
        log.info("处理评论点赞: userId={}, commentId={}, type={}", userId, commentId, type);
        
        if (commentId == null) {
            throw new IllegalArgumentException("评论ID不能为空");
        }
        
        // 验证评论是否存在
        Comment comment = commentMapper.findById(commentId);
        if (comment == null) {
            log.error("评论不存在: commentId={}", commentId);
            throw new RuntimeException("评论不存在，请检查评论ID是否正确");
        }
        
        // 定义层级：0=根评论(anime_comment)
        Integer level = 0;
        
        // 检查是否已有点赞记录（使用UserCommentLike表）
        UserCommentLike existingLike = userCommentLikeMapper.checkLikeExists(userId, commentId, level);
        log.info("现有点赞记录: {}", existingLike);
        
        if ("like".equals(type)) {
            // 点赞操作
            if (existingLike != null && existingLike.getIsDeleted() == 0) {
                // 已经点过赞且未删除，无需重复插入，直接返回成功
                log.info("已经点过赞，保持点赞状态: userId={}, commentId={}", userId, commentId);
                return true;
            } else if (existingLike != null && existingLike.getIsDeleted() == 1) {
                // 之前取消过点赞，恢复记录
                int result = userCommentLikeMapper.restoreLike(userId, commentId, level);
                if (result <= 0) {
                    throw new RuntimeException("点赞失败");
                }
                // 增加点赞数
                commentMapper.incrementLikeCount(commentId);
                log.info("恢复点赞记录: userId={}, commentId={}", userId, commentId);
            } else {
                // 首次点赞，添加新记录
                UserCommentLike userCommentLike = UserCommentLike.builder()
                    .userId(userId)
                    .commentId(commentId)
                    .level(level)
                    .build();
                int result = userCommentLikeMapper.insert(userCommentLike);
                if (result <= 0) {
                    throw new RuntimeException("点赞失败");
                }
                // 增加点赞数
                commentMapper.incrementLikeCount(commentId);
                log.info("新增点赞记录: userId={}, commentId={}", userId, commentId);
            }
        } else {
            // 取消点赞（dislike）
            if (existingLike != null && existingLike.getIsDeleted() == 0) {
                // 存在点赞记录且未删除，软删除记录
                int result = userCommentLikeMapper.deleteLike(userId, commentId, level);
                if (result <= 0) {
                    throw new RuntimeException("取消点赞失败");
                }
                // 减少点赞数
                commentMapper.decrementLikeCount(commentId);
                log.info("取消点赞: userId={}, commentId={}", userId, commentId);
            } else {
                // 没有点赞记录或已删除，无需操作
                log.info("未点过赞，无需取消: userId={}, commentId={}", userId, commentId);
            }
        }
        
        log.info("操作完成: userId={}, commentId={}, type={}", userId, commentId, type);
        
        // 清除相关缓存（使用之前查询的comment对象）
        clearCommentCache(comment.getAnimeId(), commentId);
        
        return true;
    }
    
    /**
     * 点赞/取消点赞评论或回复
     */
    @Override
    public boolean like(Long userId, LikeRequest request) {
        log.info("点赞操作: userId={}, targetType={}, targetId={}, type={}", userId, request.getTargetType(), request.getTargetId(), request.getType());
        
        // 验证目标类型
        if (!"comment".equals(request.getTargetType()) && !"reply".equals(request.getTargetType())) {
            throw new IllegalArgumentException("无效的目标类型，只能是 comment 或 reply");
        }
        
        // 验证操作类型
        if (!"like".equals(request.getType()) && !"dislike".equals(request.getType())) {
            throw new IllegalArgumentException("无效的操作类型，只能是 like 或 dislike");
        }
        
        // 验证目标ID
        if (request.getTargetId() == null) {
            throw new IllegalArgumentException("目标ID不能为空");
        }
        
        if ("comment".equals(request.getTargetType())) {
            // 处理评论点赞
            return handleCommentLike(userId, request.getTargetId(), request.getType());
        } else {
            // 处理回复点赞
            return handleReplyLike(userId, request.getTargetId(), request.getType());
        }
    }
    
    /**
     * 处理回复点赞
     */
    private boolean handleReplyLike(Long userId, Long replyId, String type) {
        log.info("处理回复点赞: userId={}, replyId={}, type={}", userId, replyId, type);
        
        if (replyId == null) {
            throw new IllegalArgumentException("回复ID不能为空");
        }
        
        // 定义层级：1=子回复(anime_comment_reply)
        Integer level = 1;
        
        // 检查是否已有点赞记录（使用UserCommentLike表，commentId字段存储的是回复ID）
        UserCommentLike existingLike = userCommentLikeMapper.checkLikeExists(userId, replyId, level);
        
        if ("like".equals(type)) {
            // 点赞操作
            if (existingLike != null && existingLike.getIsDeleted() == 0) {
                // 已经点过赞且未删除，无需重复插入，直接返回成功
                log.info("已经点过赞，保持点赞状态: userId={}, replyId={}", userId, replyId);
                return true;
            } else if (existingLike != null && existingLike.getIsDeleted() == 1) {
                // 之前取消过点赞，恢复记录
                int result = userCommentLikeMapper.restoreLike(userId, replyId, level);
                if (result <= 0) {
                    throw new RuntimeException("点赞失败");
                }
                // 增加点赞数
                commentReplyMapper.incrementLikeCount(replyId);
                log.info("恢复点赞记录: userId={}, replyId={}", userId, replyId);
            } else {
                // 首次点赞，添加新记录
                UserCommentLike userCommentLike = UserCommentLike.builder()
                    .userId(userId)
                    .commentId(replyId)
                    .level(level)
                    .build();
                int result = userCommentLikeMapper.insert(userCommentLike);
                if (result <= 0) {
                    throw new RuntimeException("点赞失败");
                }
                // 增加点赞数
                commentReplyMapper.incrementLikeCount(replyId);
                log.info("新增点赞记录: userId={}, replyId={}", userId, replyId);
            }
        } else {
            // 取消点赞（dislike）
            if (existingLike != null && existingLike.getIsDeleted() == 0) {
                // 存在点赞记录且未删除，软删除记录
                int result = userCommentLikeMapper.deleteLike(userId, replyId, level);
                if (result <= 0) {
                    throw new RuntimeException("取消点赞失败");
                }
                // 减少点赞数
                commentReplyMapper.decrementLikeCount(replyId);
                log.info("取消点赞: userId={}, replyId={}", userId, replyId);
            } else {
                // 没有点赞记录或已删除，无需操作
                log.info("未点过赞，无需取消: userId={}, replyId={}", userId, replyId);
            }
        }
        
        log.info("操作完成: userId={}, replyId={}, type={}", userId, replyId, type);
        
        // 清除相关缓存
        CommentReply reply = commentReplyMapper.findById(replyId);
        if (reply != null) {
            clearCommentCache(reply.getCommentId(), reply.getCommentId());
        }
        
        return true;
    }
    
    /**
     * 查询用户在某动漫下的点赞状态
     */
    @Override
    public UserLikeStatusResponse getUserLikeStatus(Long userId, Long animeId) {
        log.info("查询用户点赞状态: userId={}, animeId={}", userId, animeId);
        
        if (userId == null) {
            throw new IllegalArgumentException("用户ID不能为空");
        }
        
        if (animeId == null) {
            throw new IllegalArgumentException("动漫ID不能为空");
        }
        
        // 查询该动漫下的所有评论ID
        List<Comment> comments = commentMapper.findByAnimeId(animeId);
        Set<Long> commentIds = comments.stream()
            .map(Comment::getId)
            .collect(Collectors.toSet());
        
        // 收集所有回复ID
        Set<Long> replyIds = new HashSet<>();
        for (Comment comment : comments) {
            List<CommentReply> replies = commentReplyMapper.findByCommentId(comment.getId());
            if (replies != null && !replies.isEmpty()) {
                replyIds.addAll(replies.stream()
                    .map(CommentReply::getId)
                    .collect(Collectors.toSet()));
            }
        }
        
        // 批量查询用户已点赞的评论（一次性查询）
        Set<Long> likedCommentIds = new HashSet<>();
        if (!commentIds.isEmpty()) {
            Integer commentLevel = 0; // 根评论层级
            List<UserCommentLike> likedComments = userCommentLikeMapper.findLikedCommentIdsByUserAndAnime(
                userId, new java.util.ArrayList<>(commentIds), commentLevel
            );
            likedCommentIds = likedComments.stream()
                .map(UserCommentLike::getCommentId)
                .collect(Collectors.toSet());
        }
        
        // 批量查询用户已点赞的回复（一次性查询）
        Set<Long> likedReplyIds = new HashSet<>();
        if (!replyIds.isEmpty()) {
            Integer replyLevel = 1; // 子回复层级
            List<UserCommentLike> likedReplies = userCommentLikeMapper.findLikedCommentIdsByUserAndAnime(
                userId, new java.util.ArrayList<>(replyIds), replyLevel
            );
            likedReplyIds = likedReplies.stream()
                .map(UserCommentLike::getCommentId)
                .collect(Collectors.toSet());
        }
        
        log.info("查询完成: likedComments={}, likedReplies={}", likedCommentIds.size(), likedReplyIds.size());
        
        return UserLikeStatusResponse.builder()
            .likedCommentIds(likedCommentIds)
            .likedReplyIds(likedReplyIds)
            .build();
    }
    
    /**
     * 清除评论相关缓存
     */
    private void clearCommentCache(Long animeId, Long commentId) {
        // 清除该动漫的评论列表缓存
        String commentKey = String.format(CacheKeyConstants.COMMENT_ANIME, animeId);
        cacheService.delete(commentKey);
        
        // 清除该评论的回复列表缓存
        if (commentId != null) {
            String replyKey = String.format(CacheKeyConstants.COMMENT_REPLY, commentId);
            cacheService.delete(replyKey);
        }
        
        // 清除动漫详情缓存（因为包含评论信息）
        String detailKey = String.format(CacheKeyConstants.ANIME_DETAIL, animeId);
        cacheService.delete(detailKey);
        
        log.info("已清除动漫{}的评论缓存", animeId);
    }
}
