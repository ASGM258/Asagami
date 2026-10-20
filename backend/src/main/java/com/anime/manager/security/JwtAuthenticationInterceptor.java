package com.anime.manager.security;

import com.anime.manager.common.Result;
import com.anime.manager.common.ResultCode;
import com.anime.manager.common.UserContext;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.jspecify.annotations.NonNull;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * JWT认证拦截器
 * 拦截请求并验证JWT Token
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthenticationInterceptor implements HandlerInterceptor {

    private final JwtUtil jwtUtil;
    private final ObjectMapper objectMapper = new ObjectMapper();



    @Override
    public boolean preHandle(HttpServletRequest request, @NonNull HttpServletResponse response, @NonNull Object handler) throws Exception {
        String path = request.getRequestURI();
        
        // 放行登录和注册接口
        if ("/api/auth/login".equals(path) || "/api/auth/register".equals(path)) {
            return true;
        }
        
        // 获取Authorization头
        String authHeader = request.getHeader("Authorization");
        
        // 检查Token是否存在
        if (authHeader == null ) {
            log.warn("请求未携带Token: {}", path);
            sendErrorResponse(response, ResultCode.UNAUTHORIZED, "请先登录");
            return false;
        }
        if(!authHeader.startsWith("Bearer "))
        {
            log.warn("111111111111请求未携带Token: {}", path);
            sendErrorResponse(response, ResultCode.UNAUTHORIZED, "请先登录");
            return false;
        }
        
        // 提取Token
        String token = authHeader.substring(7);
        
        // 检查Token是否过期
        if (jwtUtil.isTokenExpired(token)) {
            log.warn("Token已过期: {}", path);
            sendErrorResponse(response, ResultCode.TOKEN_EXPIRED, "Token已过期，请重新登录");
            return false;
        }
        
        // 验证Token
        if (!jwtUtil.validateToken(token)) {
            log.warn("Token验证失败: {}", path);
            sendErrorResponse(response, ResultCode.TOKEN_INVALID, "Token无效");
            return false;
        }
        
        // Token有效，将用户信息存入request属性和ThreadLocal
        Long userId = jwtUtil.getUserIdFromToken(token);
        String username = jwtUtil.getUsernameFromToken(token);
        request.setAttribute("userId", userId);
        request.setAttribute("username", username);
        
        // 将用户ID存入ThreadLocal
        UserContext.setUserId(userId);
        
        log.debug("Token验证成功: userId={}, username={}, path={}", userId, username, path);
        return true;
    }
    
    @Override
    public void afterCompletion(@NonNull HttpServletRequest request, @NonNull HttpServletResponse response, 
                                @NonNull Object handler, Exception ex) throws Exception {
        // 请求结束后清除ThreadLocal，防止内存泄漏
        UserContext.clear();
    }
    
    private void sendErrorResponse(HttpServletResponse response, ResultCode resultCode, String message) throws Exception {
        response.setStatus(HttpServletResponse.SC_OK);
        response.setContentType("application/json;charset=UTF-8");
        
        Result<Void> result = Result.error(resultCode, message);
        response.getWriter().write(objectMapper.writeValueAsString(result));
    }
}
