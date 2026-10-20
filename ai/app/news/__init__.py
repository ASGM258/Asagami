"""
资讯业务模块

对外提供：
- `NewsService`：运行智能体工作流 + 提供前端查询接口
- `build_default_fetcher`：构造「AniNewsAPI + 备用 RSS」的抓取器
- `build_news_workflow`：构建 LangGraph 工作流

模块划分：
    fetchers.py    抓取源适配与归一化
    nodes.py       四个 agent 节点（抓取/翻译/摘要/审核）
    graph.py       LangGraph 拓扑与路由
    repository.py  MySQL 读写
    service.py     业务编排
    scheduler.py   定时任务
"""

from app.news.fetchers import NewsItem, build_default_fetcher
from app.news.graph import build_news_workflow
from app.news.repository import NewsRepository
from app.news.service import NewsService, get_news_service, init_news_service

__all__ = [
    "NewsItem",
    "NewsRepository",
    "NewsService",
    "build_default_fetcher",
    "build_news_workflow",
    "get_news_service",
    "init_news_service",
]
