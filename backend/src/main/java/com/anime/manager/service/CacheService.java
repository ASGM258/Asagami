package com.anime.manager.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * 缓存服务工具类
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CacheService {

    private final RedisTemplate<String, Object> redisTemplate;

    /**
     * 默认缓存过期时间（小时）
     */
    private static final long DEFAULT_EXPIRE_HOURS = 1;

    /**
     * 获取缓存数据
     */
    @SuppressWarnings("unchecked")
    public <T> T get(String key) {
        try {
            return (T) redisTemplate.opsForValue().get(key);
        } catch (Exception e) {
            log.warn("获取缓存失败，将删除损坏的缓存: key={}, error={}", key, e.getMessage());
            // 删除损坏的缓存，避免持续报错
            try {
                redisTemplate.delete(key);
                log.info("已删除损坏的缓存: key={}", key);
            } catch (Exception ex) {
                log.error("删除损坏缓存失败: key={}", key, ex);
            }
            return null;
        }
    }

    /**
     * 设置缓存数据（使用默认过期时间）
     */
    public void set(String key, Object value) {
        set(key, value, DEFAULT_EXPIRE_HOURS, TimeUnit.HOURS);
    }

    /**
     * 设置缓存数据（自定义过期时间）
     */
    public void set(String key, Object value, long timeout, TimeUnit unit) {
        try {
            redisTemplate.opsForValue().set(key, value, timeout, unit);
            log.debug("设置缓存成功: key={}", key);
        } catch (Exception e) {
            log.error("设置缓存失败: key={}, error={}", key, e.getMessage());
        }
    }

    /**
     * 删除缓存
     */
    public void delete(String key) {
        try {
            Boolean result = redisTemplate.delete(key);
            if (Boolean.TRUE.equals(result)) {
                log.debug("删除缓存成功: key={}", key);
            }
        } catch (Exception e) {
            log.error("删除缓存失败: key={}, error={}", key, e.getMessage());
        }
    }

    /**
     * 批量删除缓存（支持通配符）
     */
    public void deleteByPattern(String pattern) {
        try {
            Set<String> keys = redisTemplate.keys(pattern);
            if (keys != null && !keys.isEmpty()) {
                Long count = redisTemplate.delete(keys);
                log.info("批量删除缓存成功: pattern={}, 删除数量={}, keys={}", pattern, count, keys);
            } else {
                log.debug("未找到匹配的缓存: pattern={}", pattern);
            }
        } catch (Exception e) {
            log.error("批量删除缓存失败: pattern={}, error={}", pattern, e.getMessage());
        }
    }

    /**
     * 判断key是否存在
     */
    public boolean hasKey(String key) {
        try {
            Boolean result = redisTemplate.hasKey(key);
            return Boolean.TRUE.equals(result);
        } catch (Exception e) {
            log.error("检查缓存key失败: key={}, error={}", key, e.getMessage());
            return false;
        }
    }

    /**
     * 设置缓存过期时间
     */
    public void expire(String key, long timeout, TimeUnit unit) {
        try {
            redisTemplate.expire(key, timeout, unit);
        } catch (Exception e) {
            log.error("设置缓存过期时间失败: key={}, error={}", key, e.getMessage());
        }
    }

    /**
     * 清除所有缓存（危险操作，慎用）
     * 
     * @return 删除的key数量
     */
    public Long clearAll() {
        try {
            Set<String> keys = redisTemplate.keys("*");
            if (keys != null && !keys.isEmpty()) {
                Long count = redisTemplate.delete(keys);
                log.warn("⚠️ 已清除所有缓存: 删除数量={}", count);
                return count;
            } else {
                log.info("没有需要清除的缓存");
                return 0L;
            }
        } catch (Exception e) {
            log.error("清除所有缓存失败: error={}", e.getMessage(), e);
            throw new RuntimeException("清除缓存失败: " + e.getMessage());
        }
    }
}
