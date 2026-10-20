"""
资讯定时任务

使用 APScheduler 的 BackgroundScheduler，由 NEWS_SCHEDULER_ENABLED 控制是否启用，
执行周期由 NEWS_SCHEDULER_CRON 配置（cron 表达式，默认每天 6 点）。
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import Settings

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

JOB_ID = "news_workflow"


def start_news_scheduler(settings: Settings, job) -> BackgroundScheduler | None:
    """
    启动资讯定时任务

    Args:
        settings: 配置
        job: 无参可调用对象，执行一次资讯工作流

    Returns:
        已启动的调度器；未启用时返回 None
    """
    global _scheduler

    if not settings.news_scheduler_enabled:
        logger.info("资讯定时任务未启用（NEWS_SCHEDULER_ENABLED=false）")
        return None

    if _scheduler is not None:
        return _scheduler

    try:
        trigger = CronTrigger.from_crontab(settings.news_scheduler_cron)
    except ValueError as exc:
        logger.error(
            "资讯定时任务 cron 表达式非法: %r (%s)，已跳过启动",
            settings.news_scheduler_cron,
            exc,
        )
        return None

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        job,
        trigger=trigger,
        id=JOB_ID,
        name="资讯抓取工作流",
        replace_existing=True,
        max_instances=1,  # 避免上一轮未结束就重复触发
        coalesce=True,  # 错过的执行合并为一次
    )
    scheduler.start()

    _scheduler = scheduler
    logger.info("资讯定时任务已启动: cron=%s", settings.news_scheduler_cron)
    return scheduler


def shutdown_news_scheduler() -> None:
    """停止资讯定时任务"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("资讯定时任务已停止")
