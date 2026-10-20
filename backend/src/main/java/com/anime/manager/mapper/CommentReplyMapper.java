package com.anime.manager.mapper;

import com.anime.manager.entity.CommentReply;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 评论回复Mapper接口
 */
@Mapper
public interface CommentReplyMapper {
    
    /**
     * 根据回复ID查询单个回复
     * 
     * @param id 回复ID
     * @return 回复对象
     */
    CommentReply findById(@Param("id") Long id);
    
    /**
     * 根据主评论ID查询所有回复（包括子回复）
     * 
     * @param commentId 主评论ID
     * @return 回复列表
     */
    List<CommentReply> findByCommentId(@Param("commentId") Long commentId);
    
    /**
     * 插入评论回复
     * 
     * @param reply 回复对象
     * @return 影响行数
     */
    int insert(CommentReply reply);
    
    /**
     * 删除回复
     * 
     * @param id 回复ID
     * @return 影响行数
     */
    int deleteById(@Param("id") Long id);
    
    /**
     * 根据父回复ID删除所有子回复
     * 
     * @param parentReplyId 父回复ID
     * @return 影响行数
     */
    int deleteByParentReplyId(@Param("parentReplyId") Long parentReplyId);
    
    /**
     * 更新回复内容
     * 
     * @param id 回复ID
     * @param content 新的回复内容
     * @return 影响行数
     */
    int updateContent(@Param("id") Long id, @Param("content") String content);
    
    /**
     * 增加点赞数
     * 
     * @param id 回复ID
     * @return 影响行数
     */
    int incrementLikeCount(@Param("id") Long id);
    
    /**
     * 减少点赞数
     * 
     * @param id 回复ID
     * @return 影响行数
     */
    int decrementLikeCount(@Param("id") Long id);
    
    /**
     * 增加点踩数
     * 
     * @param id 回复ID
     * @return 影响行数
     */
    int incrementDislikeCount(@Param("id") Long id);
    
    /**
     * 减少点踩数
     * 
     * @param id 回复ID
     * @return 影响行数
     */
    int decrementDislikeCount(@Param("id") Long id);
}
