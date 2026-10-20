package com.anime.manager.mapper;

import com.anime.manager.entity.CharacterComment;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 角色评论Mapper接口
 */
@Mapper
public interface CharacterCommentMapper {
    
    /**
     * 插入评论
     */
    int insert(CharacterComment comment);
    
    /**
     * 根据ID查询评论
     */
    CharacterComment findById(@Param("id") Long id);
    
    /**
     * 根据角色ID查询评论列表
     */
    List<CharacterComment> findByCharacterId(@Param("characterId") Long characterId);
    
    /**
     * 更新评论内容
     */
    int updateContent(@Param("id") Long id, @Param("content") String content);
    
    /**
     * 删除评论
     */
    int deleteById(@Param("id") Long id);
    
    /**
     * 增加点赞数
     */
    int incrementLikeCount(@Param("id") Long id);
    
    /**
     * 减少点赞数
     */
    int decrementLikeCount(@Param("id") Long id);
}
