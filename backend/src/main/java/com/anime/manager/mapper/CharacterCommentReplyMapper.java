package com.anime.manager.mapper;

import com.anime.manager.entity.CharacterCommentReply;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 角色评论回复Mapper接口
 */
@Mapper
public interface CharacterCommentReplyMapper {
    
    /**
     * 插入回复
     */
    int insert(CharacterCommentReply reply);
    
    /**
     * 根据ID查询回复
     */
    CharacterCommentReply findById(@Param("id") Long id);
    
    /**
     * 根据评论ID查询回复列表
     */
    List<CharacterCommentReply> findByCommentId(@Param("commentId") Long commentId);
    
    /**
     * 更新回复内容
     */
    int updateContent(@Param("id") Long id, @Param("content") String content);
    
    /**
     * 删除回复
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
    
    /**
     * 根据父回复ID删除所有子回复
     */
    int deleteByParentReplyId(@Param("parentReplyId") Long parentReplyId);
}
