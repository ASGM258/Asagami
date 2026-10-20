package com.anime.manager.mapper;

import com.anime.manager.entity.UserCommentLike;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * 用户评论点赞Mapper接口
 */
@Mapper
public interface UserCommentLikeMapper {
    
    /**
     * 检查用户是否已对某条评论点赞
     * 
     * @param userId 用户ID
     * @param commentId 评论ID（可以是主评论或回复的ID）
     * @param level 层级：0=根评论(anime_comment)，1=子回复(anime_comment_reply)
     * @return 存在返回UserCommentLike对象，不存在返回null
     */
    UserCommentLike checkLikeExists(@Param("userId") Long userId, @Param("commentId") Long commentId, @Param("level") Integer level);
    
    /**
     * 添加点赞记录
     * 
     * @param userCommentLike 点赞记录对象
     * @return 影响行数
     */
    int insert(UserCommentLike userCommentLike);
    
    /**
     * 删除点赞记录（软删除）
     * 
     * @param userId 用户ID
     * @param commentId 评论ID
     * @param level 层级：0=根评论(anime_comment)，1=子回复(anime_comment_reply)
     * @return 影响行数
     */
    int deleteLike(@Param("userId") Long userId, @Param("commentId") Long commentId, @Param("level") Integer level);
    
    /**
     * 恢复点赞记录（取消软删除）
     * 
     * @param userId 用户ID
     * @param commentId 评论ID
     * @param level 层级：0=根评论(anime_comment)，1=子回复(anime_comment_reply)
     * @return 影响行数
     */
    int restoreLike(@Param("userId") Long userId, @Param("commentId") Long commentId, @Param("level") Integer level);
    
    /**
     * 批量查询用户在某动漫下的点赞记录
     * 
     * @param userId 用户ID
     * @param commentIds 评论ID列表
     * @param level 层级：0=根评论，1=子回复
     * @return 点赞记录列表
     */
    java.util.List<UserCommentLike> findLikedCommentIdsByUserAndAnime(
        @Param("userId") Long userId, 
        @Param("commentIds") java.util.List<Long> commentIds, 
        @Param("level") Integer level
    );
}
