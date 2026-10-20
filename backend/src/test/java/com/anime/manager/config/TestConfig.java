package com.anime.manager.config;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

/**
 * 测试配置类
 * 确保测试时能正确扫描到所有Bean
 */
@SpringBootApplication
@ComponentScan(basePackages = {"dwk.learn.backend", "com.anime.manager"})
@MapperScan("com.anime.manager.mapper")
public class TestConfig {
}
