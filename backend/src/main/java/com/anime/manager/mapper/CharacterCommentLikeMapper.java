package com.anime.manager.mapper;

import com.anime.manager.entity.CharacterCommentLike;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * 角色评论点赞Mapper接口
 */
@Mapper
public interface CharacterCommentLikeMapper {
    
    /**
     * 插入点赞记录
     */
    int insert(CharacterCommentLike like);
    
    /**
     * 查询用户点赞记录
     */
    CharacterCommentLike findByUserIdAndCommentId(
        @Param("userId") Long userId, 
        @Param("commentId") Long commentId,
        @Param("level") Integer level
    );
    
    /**
     * 软删除点赞记录
     */
    int deleteLike(
        @Param("userId") Long userId, 
        @Param("commentId") Long commentId,
        @Param("level") Integer level
    );
    
    /**
     * 恢复点赞记录（将is_deleted设为0）
     */
    int restoreLike(
        @Param("userId") Long userId, 
        @Param("commentId") Long commentId,
        @Param("level") Integer level
    );
    
    /**
     * 批量查询用户在某角色下的点赞记录
     * 
     * @param userId 用户ID
     * @param commentIds 评论ID列表
     * @param level 层级：0=根评论，1=子回复
     * @return 点赞记录列表
     */
    java.util.List<CharacterCommentLike> findLikedCommentIdsByUserAndCharacter(
        @Param("userId") Long userId, 
        @Param("commentIds") java.util.List<Long> commentIds, 
        @Param("level") Integer level
    );
}
