package com.anime.manager.config;

import com.anime.manager.security.JwtAuthenticationInterceptor;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.ClientHttpRequestFactory;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Web MVC配置类
 * 配置CORS跨域、拦截器等
 */
@Configuration
@RequiredArgsConstructor
public class WebMvcConfig implements WebMvcConfigurer {
    
    private final JwtAuthenticationInterceptor jwtAuthenticationInterceptor;
    
    /**
     * 配置RestTemplate Bean（单例模式）
     * 设置超时时间，避免请求长时间挂起
     */
    @Bean
    public RestTemplate restTemplate() {
        ClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        // 连接超时时间：10秒（考虑到网络波动）
        ((SimpleClientHttpRequestFactory) factory).setConnectTimeout(10000);
        // 读取超时时间：30秒（第三方数据源如 AniList 有时响应较慢）
        ((SimpleClientHttpRequestFactory) factory).setReadTimeout(30000);
        return new RestTemplate(factory);
    }
    
    /**
     * 配置CORS跨域
     */
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
                .allowedOriginPatterns("*")  // 允许所有来源
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH")
                .allowedHeaders("*")
                .allowCredentials(true)  // 允许携带凭证
                .maxAge(3600);  // 预检请求缓存时间（秒）
    }
    
    /**
     * 注册拦截器
     */
    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(jwtAuthenticationInterceptor)
                .addPathPatterns("/api/**")  // 拦截所有/api开头的请求
                .excludePathPatterns(
                        "/api/auth/login",          // 排除登录接口
                        "/api/auth/register"      // 排除注册接口
                );
    }
}
