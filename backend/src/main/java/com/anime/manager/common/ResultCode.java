package com.anime.manager.common;

import lombok.Getter;

/**
 * 响应码枚举
 * 定义系统中所有可能的响应状态码
 */
@Getter
public enum ResultCode {
    
    // 成功
    SUCCESS(200, "操作成功"),
    
    // 客户端错误 (4xx)
    BAD_REQUEST(400, "请求参数错误"),
    UNAUTHORIZED(401, "未授权，请先登录"),
    FORBIDDEN(403, "禁止访问"),
    NOT_FOUND(404, "资源不存在"),
    METHOD_NOT_ALLOWED(405, "请求方法不允许"),
    CONFLICT(409, "资源冲突"),
    
    // 服务器错误 (5xx)
    ERROR(500, "服务器内部错误"),
    SERVICE_UNAVAILABLE(503, "服务不可用"),
    
    // 业务错误码 (1xxx - 用户相关, 2xxx - 动漫相关, 3xxx - 观看记录相关)
    USER_ALREADY_EXISTS(1001, "用户已存在"),
    USER_NOT_FOUND(1002, "用户不存在"),
    USERNAME_OR_PASSWORD_ERROR(1003, "用户名或密码错误"),
    TOKEN_INVALID(1004, "Token无效或已过期"),
    TOKEN_EXPIRED(1005, "Token已过期"),
    
    ANIME_NOT_FOUND(2001, "动漫不存在"),
    ANIME_ALREADY_EXISTS(2002, "动漫已存在"),
    
    WATCH_RECORD_NOT_FOUND(3001, "观看记录不存在"),
    WATCH_RECORD_ALREADY_EXISTS(3002, "观看记录已存在"),
    WATCH_STATUS_INVALID(3003, "观看状态无效");
    
    /**
     * 响应码
     */
    private final Integer code;
    
    /**
     * 响应消息
     */
    private final String message;
    
    /**
     * 构造函数
     */
    ResultCode(Integer code, String message) {
        this.code = code;
        this.message = message;
    }
}
