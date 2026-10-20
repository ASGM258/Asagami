package com.anime.manager.service.impl;

import com.anime.manager.common.ResultCode;
import com.anime.manager.dto.AuthResponse;
import com.anime.manager.dto.LoginRequest;
import com.anime.manager.dto.RegisterRequest;
import com.anime.manager.dto.UserProfileUpdateRequest;
import com.anime.manager.entity.User;
import com.anime.manager.exception.BusinessException;
import com.anime.manager.mapper.UserMapper;
import com.anime.manager.security.JwtUtil;
import com.anime.manager.service.AuthService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 认证服务实现类
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {
    
    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtil jwtUtil;
    
    /**
     * 用户注册
     */
    @Override
    @Transactional
    public AuthResponse register(RegisterRequest request) {
        log.info("用户注册: username={}, email={}", request.getUsername(), request.getEmail());
        
        // 检查用户名是否已存在
        if (userMapper.findByUsername(request.getUsername()) != null) {
            throw new BusinessException(ResultCode.USER_ALREADY_EXISTS, "用户名已存在");
        }
        
        // 检查邮箱是否已存在
        if (userMapper.findByEmail(request.getEmail()) != null) {
            throw new BusinessException(ResultCode.USER_ALREADY_EXISTS, "邮箱已被注册");
        }
        
        // 创建用户
        User user = new User();
        user.setUsername(request.getUsername());
        user.setEmail(request.getEmail());
        user.setPassword(passwordEncoder.encode(request.getPassword())); // BCrypt加密
        user.setNickname(request.getNickname() != null ? request.getNickname() : request.getUsername());
        
        // 插入数据库
        userMapper.insert(user);
        
        log.info("用户注册成功: userId={}, username={}", user.getId(), user.getUsername());
        
        // 生成Token并返回
        return buildAuthResponse(user);
    }
    
    /**
     * 用户登录
     */
    @Override
    public AuthResponse login(LoginRequest request) {
        log.info("用户登录: username={}", request.getUsername());
        
        // 查询用户（支持用户名或邮箱登录）
        User user = userMapper.findByUsername(request.getUsername());
        if (user == null) {
            user = userMapper.findByEmail(request.getUsername());
        }
        
        // 用户不存在或密码错误
        if (user == null || !passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new BusinessException(ResultCode.USERNAME_OR_PASSWORD_ERROR);
        }
        
        log.info("用户登录成功: userId={}, username={}", user.getId(), user.getUsername());
        
        // 生成Token并返回
        return buildAuthResponse(user);
    }
    
    /**
     * 获取用户信息
     */
    @Override
    public User getUserProfile(Long userId) {
        User user = userMapper.findById(userId);
        if (user == null) {
            throw new BusinessException(ResultCode.USER_NOT_FOUND);
        }
        return user;
    }
    
    /**
     * 更新用户信息
     */
    @Override
    @Transactional
    public User updateUserProfile(Long userId, UserProfileUpdateRequest request) {
        User user = userMapper.findById(userId);
        if (user == null) {
            throw new BusinessException(ResultCode.USER_NOT_FOUND);
        }
        
        // 如果更新邮箱，检查是否已被使用
        if (request.getEmail() != null && !request.getEmail().equals(user.getEmail())) {
            User existingUser = userMapper.findByEmail(request.getEmail());
            if (existingUser != null) {
                throw new BusinessException(ResultCode.USER_ALREADY_EXISTS, "邮箱已被使用");
            }
            user.setEmail(request.getEmail());
        }
        
        // 更新其他字段
        if (request.getNickname() != null) {
            user.setNickname(request.getNickname());
        }
        if (request.getAvatar() != null) {
            user.setAvatar(request.getAvatar());
        }
        
        // 处理密码修改
        if (request.getCurrentPassword() != null || request.getNewPassword() != null) {
            // 必须同时提供当前密码和新密码
            if (request.getCurrentPassword() == null || request.getNewPassword() == null) {
                throw new BusinessException(ResultCode.BAD_REQUEST, "修改密码需要同时提供当前密码和新密码");
            }
            
            // 验证当前密码是否正确
            if (!passwordEncoder.matches(request.getCurrentPassword(), user.getPassword())) {
                throw new BusinessException(ResultCode.USERNAME_OR_PASSWORD_ERROR, "当前密码错误");
            }
            
            // 验证新密码不能与当前密码相同
            if (passwordEncoder.matches(request.getNewPassword(), user.getPassword())) {
                throw new BusinessException(ResultCode.BAD_REQUEST, "新密码不能与当前密码相同");
            }
            
            // 更新密码
            userMapper.updatePassword(userId, passwordEncoder.encode(request.getNewPassword()));
            log.info("用户密码修改成功: userId={}", userId);
        }
        
        // 执行更新（如果昵称、邮箱、头像有变化）
        if (request.getNickname() != null || request.getEmail() != null || request.getAvatar() != null) {
            userMapper.update(user);
        }
        
        log.info("用户信息更新成功: userId={}", userId);
        
        return userMapper.findById(userId);
    }
    
    /**
     * 构建认证响应
     */
    private AuthResponse buildAuthResponse(User user) {
        String token = jwtUtil.generateToken(user.getId(), user.getUsername());
        
        return AuthResponse.builder()
                .accessToken(token)
                .tokenType("Bearer")
                .userId(user.getId())
                .username(user.getUsername())
                .email(user.getEmail())
                .nickname(user.getNickname())
                .avatar(user.getAvatar())
                .build();
    }
}
