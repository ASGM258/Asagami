"""
资讯接口的数据模型

说明：资讯响应体必须原样输出驼峰字段，且列表分页的键名就是 `list`
（与前端 PageResponse 一致）。用 Pydantic 的 BaseModel 会与内建 list
类型冲突，因此响应结构改用 TypedDict 描述，仅用于类型提示与 OpenAPI 文档，
实际响应由 app.core.responses 统一构造。
"""

from __future__ import annotations

from typing import Generic, TypedDict, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class NewsDetailQueryRequest(BaseModel):
    """资讯详情请求体"""

    newsId: int = Field(..., description="资讯ID")


class NewsListItem(TypedDict, total=False):
    """资讯列表项（对齐前端 NewsItem）"""

    id: int
    title: str
    coverImage: str
    summary: str
    category: str
    source: str
    author: str
    publishTime: str
    tags: list[str]
    viewCount: int


class NewsDetailItem(NewsListItem, total=False):
    """资讯详情项（对齐前端 NewsDetail）"""

    content: str
    relatedAnimeId: int | None
    relatedAnimeTitle: str | None


class NewsListData(TypedDict):
    """资讯列表 data 部分（对齐前端 PageResponse<NewsItem>）"""

    total: int
    pages: int
    pageNum: int
    pageSize: int
    list: list[NewsListItem]


class NewsCategoryItem(TypedDict):
    """资讯分类项（对齐前端 NewsCategory）"""

    key: str
    name: str
    count: int


class NewsRefreshData(TypedDict):
    """手动触发结果"""

    accepted: bool
    message: str


class SuccessEnvelope(TypedDict, Generic[T]):
    """统一成功外壳（与既有接口保持一致）"""

    success: bool
    message: str
    timestamp: float
    data: T
