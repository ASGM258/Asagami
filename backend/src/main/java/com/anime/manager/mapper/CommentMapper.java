package com.anime.manager.mapper;

import com.anime.manager.entity.Comment;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 评论Mapper接口
 */
@Mapper
public interface CommentMapper {
    
    /**
     * 根据动漫ID查询评论列表（按时间倒序）
     * 
     * @param animeId 动漫ID
     * @return 评论列表
     */
    List<Comment> findByAnimeId(@Param("animeId") Long animeId);
    
    /**
     * 插入评论
     * 
     * @param comment 评论对象
     * @return 影响行数
     */
    int insert(Comment comment);
    
    /**
     * 删除评论
     * 
     * @param id 评论ID
     * @return 影响行数
     */
    int deleteById(@Param("id") Long id);
    
    /**
     * 更新评论内容
     * 
     * @param id 评论ID
     * @param content 新的评论内容
     * @return 影响行数
     */
    int updateContent(@Param("id") Long id, @Param("content") String content);
    
    /**
     * 根据ID查询评论
     * 
     * @param id 评论ID
     * @return 评论对象
     */
    Comment findById(@Param("id") Long id);
    
    /**
     * 增加点赞数
     * 
     * @param id 评论ID
     * @return 影响行数
     */
    int incrementLikeCount(@Param("id") Long id);
    
    /**
     * 减少点赞数
     * 
     * @param id 评论ID
     * @return 影响行数
     */
    int decrementLikeCount(@Param("id") Long id);
    
    /**
     * 增加点踩数
     * 
     * @param id 评论ID
     * @return 影响行数
     */
    int incrementDislikeCount(@Param("id") Long id);
    
    /**
     * 减少点踩数
     * 
     * @param id 评论ID
     * @return 影响行数
     */
    int decrementDislikeCount(@Param("id") Long id);
}
