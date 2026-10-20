package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.dto.AuthResponse;
import com.anime.manager.dto.LoginRequest;
import com.anime.manager.dto.RegisterRequest;
import com.anime.manager.dto.UserProfileUpdateRequest;
import com.anime.manager.entity.User;
import com.anime.manager.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

/**
 * 认证控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {
    
    private final AuthService authService;
    
    /**
     * 用户注册
     */
    @PostMapping("/register")
    public Result<AuthResponse> register(@Valid @RequestBody RegisterRequest request) {
        log.info("收到注册请求: username={}", request.getUsername());
        AuthResponse response = authService.register(request);
        return Result.success("注册成功", response);
    }
    
    /**
     * 用户登录
     */
    @PostMapping("/login")
    public Result<AuthResponse> login(@Valid @RequestBody LoginRequest request) {
        log.info("收到登录请求: username={}", request.getUsername());
        AuthResponse response = authService.login(request);
        return Result.success("登录成功", response);
    }
    
    /**
     * 获取用户信息
     */
    @GetMapping("/profile")
    public Result<User> getProfile(HttpServletRequest request) {
        Long userId = (Long) request.getAttribute("userId");
        User user = authService.getUserProfile(userId);
        // 隐藏密码字段
        user.setPassword(null);
        return Result.success(user);
    }
    
    /**
     * 更新用户信息
     */
    @PutMapping("/profile")
    public Result<User> updateProfile(
            HttpServletRequest request,
            @Valid @RequestBody UserProfileUpdateRequest updateRequest) {
        Long userId = (Long) request.getAttribute("userId");
        User user = authService.updateUserProfile(userId, updateRequest);
        // 隐藏密码字段
        user.setPassword(null);
        return Result.success("更新成功", user);
    }
}
