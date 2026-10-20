package com.anime.manager.common;

/**
 * 用户上下文工具类
 * 使用ThreadLocal存储当前请求的用户信息
 */
public class UserContext {
    
    private static final ThreadLocal<Long> USER_ID_HOLDER = new ThreadLocal<>();
    
    /**
     * 设置当前用户ID
     * 
     * @param userId 用户ID
     */
    public static void setUserId(Long userId) {
        USER_ID_HOLDER.set(userId);
    }
    
    /**
     * 获取当前用户ID
     * 
     * @return 用户ID
     */
    public static Long getUserId() {
        return USER_ID_HOLDER.get();
    }
    
    /**
     * 清除当前用户ID
     * 防止内存泄漏，必须在请求结束后调用
     */
    public static void clear() {
        USER_ID_HOLDER.remove();
    }
}
