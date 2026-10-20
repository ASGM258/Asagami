package com.anime.manager.service;

import com.anime.manager.dto.AuthResponse;
import com.anime.manager.dto.LoginRequest;
import com.anime.manager.dto.RegisterRequest;
import com.anime.manager.dto.UserProfileUpdateRequest;
import com.anime.manager.entity.User;

/**
 * 认证服务接口
 */
public interface AuthService {
    
    /**
     * 用户注册
     * 
     * @param request 注册请求
     * @return 认证响应
     */
    AuthResponse register(RegisterRequest request);
    
    /**
     * 用户登录
     * 
     * @param request 登录请求
     * @return 认证响应
     */
    AuthResponse login(LoginRequest request);
    
    /**
     * 获取用户信息
     * 
     * @param userId 用户ID
     * @return 用户信息
     */
    User getUserProfile(Long userId);
    
    /**
     * 更新用户信息
     * 
     * @param userId 用户ID
     * @param request 更新请求
     * @return 更新后的用户信息
     */
    User updateUserProfile(Long userId, UserProfileUpdateRequest request);
}
