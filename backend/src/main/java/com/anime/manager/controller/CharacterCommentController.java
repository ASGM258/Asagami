package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.common.UserContext;
import com.anime.manager.dto.CommentReplyRequest;
import com.anime.manager.dto.LikeRequest;
import com.anime.manager.service.CharacterCommentService;
import com.anime.manager.vo.CharacterCommentResponse;
import com.anime.manager.vo.CommentReplyResponse;
import com.anime.manager.vo.UserLikeStatusResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 角色评论管理控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/character/comment")
@RequiredArgsConstructor
public class CharacterCommentController {
    
    private final CharacterCommentService characterCommentService;
    
    /**
     * 发表评论
     * 
     * @param characterId 角色ID
     * @param content 评论内容
     * @return 评论响应（包含评论信息和评论人信息）
     */
    @PostMapping("/add/{characterId}")
    public Result<CharacterCommentResponse> addComment(
            @PathVariable Long characterId,
            @RequestBody String content) {
        log.info("收到发表评论请求: characterId={}", characterId);
        
        try {
            CharacterCommentResponse response = characterCommentService.addComment(characterId, content);
            return Result.success("评论发表成功", response);
        } catch (IllegalArgumentException e) {
            log.error("参数错误: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (RuntimeException e) {
            log.error("发表评论失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
    
    /**
     * 更新评论
     * 
     * @param commentId 评论ID
     * @param content 新的评论内容
     * @return 操作结果
     */
    @PutMapping("/update/{commentId}")
    public Result<Boolean> updateComment(
            @PathVariable Long commentId,
            @RequestBody String content) {
        log.info("收到更新评论请求: commentId={}", commentId);
        
        try {
            boolean success = characterCommentService.updateComment(commentId, content);
            if (success) {
                return Result.success("更新成功", true);
            } else {
                return Result.error("更新失败");
            }
        } catch (IllegalArgumentException e) {
            log.error("参数错误: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (RuntimeException e) {
            log.error("更新评论失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
    
    /**
     * 删除评论
     * 
     * @param commentId 评论ID
     * @return 操作结果
     */
    @DeleteMapping("/delete/{commentId}")
    public Result<Boolean> deleteComment(@PathVariable Long commentId) {
        log.info("收到删除评论请求: commentId={}", commentId);
        
        try {
            boolean success = characterCommentService.deleteComment(commentId);
            if (success) {
                return Result.success("删除成功", true);
            } else {
                return Result.error("删除失败");
            }
        } catch (IllegalArgumentException e) {
            log.error("参数错误: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (RuntimeException e) {
            log.error("删除评论失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
    
    /**
     * 查询某角色的所有评论（包含回复）
     * 
     * @param characterId 角色ID
     * @return 评论列表（包含回复）
     */
    @GetMapping("/list/{characterId}")
    public Result<List<CharacterCommentResponse>> getCommentsByCharacterId(@PathVariable Long characterId) {
        log.info("收到查询评论请求: characterId={}", characterId);
        
        try {
            List<CharacterCommentResponse> comments = characterCommentService.getCommentsByCharacterId(characterId);
            return Result.success(comments);
        } catch (IllegalArgumentException e) {
            log.error("参数错误: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (RuntimeException e) {
            log.error("查询评论失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
    
    /**
     * 发表评论回复
     * 
     * @param request 回复请求（包含主评论ID、父回复ID和回复内容）
     * @return 回复响应（包含回复信息和回复人信息）
     */
    @PostMapping("/reply/add")
    public Result<CommentReplyResponse> addCommentReply(@Valid @RequestBody CommentReplyRequest request) {
        log.info("收到发表回复请求: commentId={}, parentReplyId={}", request.getCommentId(), request.getParentReplyId());
        
        try {
            CommentReplyResponse response = characterCommentService.addCommentReply(request);
            return Result.success("回复发表成功", response);
        } catch (IllegalArgumentException e) {
            log.error("参数错误: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (RuntimeException e) {
            log.error("发表回复失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
    
    /**
     * 删除评论回复
     * 
     * @param replyId 回复ID
     * @return 操作结果
     */
    @DeleteMapping("/reply/delete/{replyId}")
    public Result<Boolean> deleteCommentReply(@PathVariable Long replyId) {
        log.info("收到删除回复请求: replyId={}", replyId);
        
        try {
            boolean success = characterCommentService.deleteCommentReply(replyId);
            if (success) {
                return Result.success("删除成功", true);
            } else {
                return Result.error("删除失败");
            }
        } catch (IllegalArgumentException e) {
            log.error("参数错误: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (RuntimeException e) {
            log.error("删除回复失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
    
    /**
     * 点赞/取消点赞评论或回复
     * 
     * @param request 点赞请求（包含targetType、targetId、type）
     * @return 操作结果
     */
    @PostMapping("/like")
    public Result<Boolean> like(@Valid @RequestBody LikeRequest request) {
        log.info("收到点赞请求: targetType={}, type={}", request.getTargetType(), request.getType());
        
        try {
            // 获取当前登录用户ID
            Long userId = UserContext.getUserId();
            if (userId == null) {
                return Result.error("请先登录");
            }
            
            boolean success = characterCommentService.like(userId, request);
            if (success) {
                String message = "like".equals(request.getType()) ? "点赞成功" : "取消点赞成功";
                return Result.success(message, true);
            } else {
                return Result.error("操作失败");
            }
        } catch (IllegalArgumentException e) {
            log.error("参数错误: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (RuntimeException e) {
            log.error("点赞操作失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
    
    /**
     * 查询用户在某角色下的点赞状态
     * 
     * @param characterId 角色ID
     * @return 用户点赞状态（包含已点赞的评论ID和回复ID集合）
     */
    @GetMapping("/like/status/{characterId}")
    public Result<UserLikeStatusResponse> getUserLikeStatus(@PathVariable Long characterId) {
        log.info("收到查询点赞状态请求: characterId={}", characterId);
        
        try {
            // 获取当前登录用户ID
            Long userId = UserContext.getUserId();
            if (userId == null) {
                return Result.error("请先登录");
            }
            
            UserLikeStatusResponse response = characterCommentService.getUserLikeStatus(userId, characterId);
            return Result.success(response);
        } catch (IllegalArgumentException e) {
            log.error("参数错误: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (RuntimeException e) {
            log.error("查询点赞状态失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
}
