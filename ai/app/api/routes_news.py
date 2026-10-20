"""
资讯接口

    GET  /api/news/list        资讯列表（分页，供无限滚动）
    POST /api/news/detail      资讯详情
    GET  /api/news/categories  分类列表
    POST /api/news/refresh     手动触发抓取工作流（异步执行）

响应体严格对齐前端 src/api/news.ts 与 src/types/news.ts：
- 统一外壳沿用本服务的 {success, message, timestamp, data}
- data 内部字段为驼峰命名，与前端 NewsItem / PageResponse 一致
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from starlette.concurrency import run_in_threadpool

from app.core.errors import BusinessError
from app.core.responses import success_response
from app.dependencies import get_news_service
from app.news.service import NewsService
from app.schemas.news import (
    NewsDetailItem,
    NewsDetailQueryRequest,
    NewsRefreshData,
    SuccessEnvelope,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/news", tags=["资讯"])


@router.get("/list", response_model=SuccessEnvelope, summary="获取资讯列表")
async def get_news_list(
    pageNum: int = Query(1, ge=1, description="页码（从1开始）"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    category: str | None = Query(None, description="分类筛选，空或 all 表示全部"),
    keyword: str | None = Query(None, description="关键词搜索"),
    news_service: NewsService = Depends(get_news_service),
):
    """
    获取资讯列表（分页）

    data 结构为 PageResponse<NewsItem>：{total, pages, pageNum, pageSize, list}
    """
    from starlette.concurrency import run_in_threadpool

    page = await run_in_threadpool(
        news_service.list_news, pageNum, pageSize, category, keyword
    )

    # 直接返回字典，避免 Pydantic 过滤掉前端依赖的字段
    return success_response(data=page, message="获取资讯列表成功")


@router.post(
    "/detail",
    response_model=SuccessEnvelope[NewsDetailItem],
    summary="获取资讯详情",
)
async def get_news_detail(
    payload: NewsDetailQueryRequest,
    news_service: NewsService = Depends(get_news_service),
):
    """
    获取资讯详情（含正文）

    Request Body:
        {"newsId": 1}
    """
    from starlette.concurrency import run_in_threadpool

    if not payload.newsId:
        raise BusinessError(
            message="缺少必要参数：newsId",
            error_code="MISSING_PARAMETER",
            http_status=400,
        )

    detail = await run_in_threadpool(news_service.get_detail, payload.newsId)

    if not detail:
        raise BusinessError(
            message="资讯不存在或已下架",
            error_code="NEWS_NOT_FOUND",
            http_status=404,
        )

    return success_response(data=detail, message="获取资讯详情成功")


@router.get("/categories", response_model=SuccessEnvelope, summary="获取资讯分类")
async def get_news_categories(
    news_service: NewsService = Depends(get_news_service),
):
    """
    获取分类列表（含各分类数量）

    「全部」始终位于第一位，与前端筛选标签一致。
    """
    from starlette.concurrency import run_in_threadpool

    categories = await run_in_threadpool(news_service.list_categories)
    return success_response(data=categories, message="获取分类成功")


@router.post("/refresh", response_model=SuccessEnvelope, summary="手动触发资讯抓取")
async def refresh_news(
    background_tasks: BackgroundTasks,
    limit: int | None = Query(None, ge=1, le=100, description="本次抓取条数上限"),
    repair: bool = Query(False, description="同时修复已入库但正文残缺的条目"),
    news_service: NewsService = Depends(get_news_service),
):
    """
    手动触发抓取-翻译-摘要-审核工作流

    工作流耗时较长（抓取 + 正文补全 + 多次模型调用），因此放入后台任务异步执行，
    接口立即返回已受理；前端可轮询 `/news/refresh/status` 获知进度与结果。

    `repair=true` 时，已入库但正文残缺（早于正文补全功能）的条目会重新处理，
    由 upsert 覆盖为完整正文。
    """
    if news_service.is_running():
        return success_response(
            data=NewsRefreshData(
                accepted=False,
                message="已有抓取任务正在执行，请等待其完成",
            ),
            message="任务进行中",
        )

    def _run() -> None:
        try:
            summary = news_service.run_workflow(limit, repair=repair)
            logger.info(
                "后台资讯工作流完成: run_id=%s 可发布=%d 拒绝=%d",
                summary["run_id"],
                summary["published"],
                summary["rejected"],
            )
        except Exception as exc:  # noqa: BLE001 - 后台任务需自行兜底
            logger.exception("后台资讯工作流失败: %s", exc)

    background_tasks.add_task(_run)

    data: NewsRefreshData = {
        "accepted": True,
        "message": (
            "资讯抓取任务已受理（含正文修复），正在后台执行"
            if repair
            else "资讯抓取任务已受理，正在后台执行"
        ),
    }
    return success_response(data=data, message="已触发资讯抓取")


@router.get("/refresh/status", response_model=SuccessEnvelope, summary="查询抓取任务状态")
async def refresh_status(
    news_service: NewsService = Depends(get_news_service),
):
    """
    查询抓取任务是否在执行、以及上一次运行的结果

    前端点「刷新」后轮询本接口，等到 `running=false` 再拉列表，
    避免用户以为按钮没反应。
    """
    return success_response(data=news_service.run_status(), message="查询成功")
