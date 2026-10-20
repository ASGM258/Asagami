package com.anime.manager.mapper;

import com.anime.manager.entity.User;
import org.apache.ibatis.annotations.*;

/**
 * 用户Mapper接口
 */
@Mapper
public interface UserMapper {
    
    /**
     * 根据ID查询用户
     */
    @Select("SELECT * FROM user WHERE id = #{id}")
    User findById(Long id);
    
    /**
     * 根据用户名查询用户
     */
    @Select("SELECT * FROM user WHERE username = #{username}")
    User findByUsername(String username);
    
    /**
     * 根据邮箱查询用户
     */
    @Select("SELECT * FROM user WHERE email = #{email}")
    User findByEmail(String email);
    
    /**
     * 插入用户
     */
    @Insert("INSERT INTO user(username, email, password, nickname, avatar, created_at, updated_at) " +
            "VALUES(#{username}, #{email}, #{password}, #{nickname}, #{avatar}, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(User user);
    
    /**
     * 更新用户信息（动态SQL，只更新非空字段）
     * SQL定义在 UserMapper.xml 中
     */
    int update(User user);
    
    /**
     * 更新密码
     */
    @Update("UPDATE user SET password = #{password}, updated_at = NOW() WHERE id = #{id}")
    int updatePassword(@Param("id") Long id, @Param("password") String password);
    
    /**
     * 更新用户头像
     */
    @Update("UPDATE user SET avatar = #{avatar}, updated_at = NOW() WHERE id = #{id}")
    int updateAvatar(@Param("id") Long id, @Param("avatar") String avatar);
}
