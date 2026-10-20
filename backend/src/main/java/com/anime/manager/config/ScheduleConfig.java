package com.anime.manager.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 定时任务配置类
 * 启用Spring的定时任务功能
 */
@Configuration
@EnableScheduling
public class ScheduleConfig {
    // 此配置类仅用于启用定时任务功能
    // 具体的定时任务在SeasonalScraperScheduler中定义
}
