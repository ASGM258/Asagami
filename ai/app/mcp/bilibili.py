"""
B 站 MCP 服务的领域封装

职责划分：
    stdio_client.py  —— 只管 MCP 协议（握手、列工具、调工具）
    bilibili.py      —— 管业务：关键词搜索 → 补取互动数据 → 综合排序 → 可点击链接
    tools.py         —— 暴露给 Agent 的 LangChain 工具

排序策略（用户诉求：按播放量、点赞数等综合考虑）：
搜索接口只返回播放量与弹幕数，点赞/收藏/投币需要再查一次视频详情，
因此取搜索结果的头部候选补详情，再用加权分排序：

    score = 播放 + 点赞×10 + 收藏×8 + 投币×6 + 弹幕×3 + 评论×2

权重体现了「点赞/收藏/投币是主动行为、含金量高于播放」的直觉。
最终把原始数值一并返回，让模型能解释推荐理由，而不是给个黑箱分数。
"""

import logging
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.mcp.stdio_client import McpError, McpStdioClient

logger = logging.getLogger(__name__)

#: 视频播放页地址模板
VIDEO_URL_TEMPLATE = "https://www.bilibili.com/video/{bvid}"

#: 综合评分权重（见模块说明）
SCORE_WEIGHTS = {
    "view": 1.0,
    "like": 10.0,
    "favorite": 8.0,
    "coin": 6.0,
    "danmaku": 3.0,
    "reply": 2.0,
}


@dataclass
class VideoRecommendation:
    """一条视频推荐（对模型与前端都友好的扁平结构）"""

    bvid: str
    title: str
    author: str
    url: str
    play: int = 0
    like: int = 0
    favorite: int = 0
    coin: int = 0
    danmaku: int = 0
    reply: int = 0
    duration: int = 0
    pubdate: str = ""
    description: str = ""
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ==================== 启动命令解析 ====================


def _ai_root() -> Path:
    """ai/ 目录（本文件位于 ai/app/mcp/bilibili.py）"""
    return Path(__file__).resolve().parents[2]


def resolve_command(settings: Settings) -> list[str]:
    """
    解析 MCP 服务启动命令

    优先级：
    1. `BILIBILI_MCP_COMMAND` 显式配置（可填可执行文件路径）
    2. `ai/.venv-mcp/Scripts/bili-mcp.exe`（独立 venv 安装，推荐）
    3. PATH 中的 `bili-mcp`

    Returns:
        可直接交给 subprocess 的命令列表；找不到时为空列表
    """
    args = ["--stdio"]
    configured = (settings.bilibili_mcp_command or "").strip()

    if configured:
        path = Path(configured)
        if path.exists():
            return [str(path), *args]
        # 配置的是裸命令名，交给 PATH 解析
        resolved = shutil.which(configured)
        if resolved:
            return [resolved, *args]
        logger.warning("BILIBILI_MCP_COMMAND 指向的可执行文件不存在: %s", configured)
        return []

    # 独立 venv 优先：它只装了 MCP 服务，不污染主环境
    venv_exe = _ai_root() / ".venv-mcp" / "Scripts" / "bili-mcp.exe"
    if venv_exe.exists():
        return [str(venv_exe), *args]
    venv_bin = _ai_root() / ".venv-mcp" / "bin" / "bili-mcp"
    if venv_bin.exists():
        return [str(venv_bin), *args]

    resolved = shutil.which("bili-mcp")
    if resolved:
        return [resolved, *args]

    return []


def build_env(settings: Settings) -> dict[str, str]:
    """
    构造子进程环境变量

    除 Cookie 外必须继承父进程环境（Windows 下缺 SystemRoot 会导致各种诡异失败）。
    """
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # 让子进程输出保持 UTF-8，避免中文标题在管道里变乱码
    env.setdefault("PYTHONUTF8", "1")

    if settings.bili_sessdata:
        env["BILI_SESSDATA"] = settings.bili_sessdata
    if settings.bili_bili_jct:
        env["BILI_BILI_JCT"] = settings.bili_bili_jct
    if settings.bili_buvid3:
        env["BILI_BUVID3"] = settings.bili_buvid3
    return env


# ==================== 业务封装 ====================


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _pick(mapping: dict, *keys: str) -> Any:
    """按候选键取值（不同版本字段名可能不同）"""
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def score_of(video: dict[str, Any]) -> float:
    """
    计算综合评分

    优先用详情接口的 `stat` 字段；只有搜索结果时仅播放量与弹幕可用。
    """
    stat = video.get("stat") if isinstance(video.get("stat"), dict) else {}

    def value(name: str) -> int:
        if stat and name in stat:
            return _as_int(stat.get(name))
        alias = {"view": ("play", "view"), "reply": ("reply",)}.get(name, (name,))
        return _as_int(_pick(video, *alias))

    return round(
        sum(value(name) * weight for name, weight in SCORE_WEIGHTS.items()), 1
    )


def normalize_video(raw: dict[str, Any]) -> VideoRecommendation:
    """把 MCP 返回的原始条目归一化为推荐结构"""
    bvid = str(_pick(raw, "bvid", "bvid_str") or "")
    stat = raw.get("stat") if isinstance(raw.get("stat"), dict) else {}

    def stat_value(name: str, *aliases: str) -> int:
        # 详情接口的字段在 stat 里；搜索结果直接平铺在顶层
        if name in stat:
            return _as_int(stat.get(name))
        return _as_int(_pick(raw, *(aliases or (name,))) or 0)

    return VideoRecommendation(
        bvid=bvid,
        title=str(_pick(raw, "title") or "").strip(),
        author=str(_pick(raw, "owner_name", "author", "up_name") or "").strip(),
        url=VIDEO_URL_TEMPLATE.format(bvid=bvid) if bvid else "",
        play=stat_value("view", "play", "view"),
        like=stat_value("like"),
        favorite=stat_value("favorite", "favorites"),
        coin=stat_value("coin"),
        danmaku=stat_value("danmaku"),
        reply=stat_value("reply"),
        duration=_as_int(_pick(raw, "duration")),
        pubdate=str(_pick(raw, "pubdate", "created") or ""),
        description=str(_pick(raw, "description", "desc") or "").strip(),
        score=score_of(raw),
    )


class BilibiliMcpService:
    """
    B 站 MCP 业务服务

    单例使用（进程级），内部维护一个常驻的 MCP 子进程。
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: McpStdioClient | None = None

    # ==================== 客户端 ====================

    def _client_or_none(self) -> McpStdioClient | None:
        if not self._settings.bilibili_mcp_enabled:
            return None
        if self._client is not None:
            return self._client

        command = resolve_command(self._settings)
        if not command:
            logger.warning(
                "未找到 bili-mcp 可执行文件。请安装："
                "python -m venv .venv-mcp && .venv-mcp\\Scripts\\pip install bilibili-cognitive-server"
            )
            return None

        self._client = McpStdioClient(
            command,
            env=build_env(self._settings),
            timeout=self._settings.bilibili_mcp_timeout,
        )
        return self._client

    def close(self) -> None:
        """关闭 MCP 子进程（应用退出时调用）"""
        if self._client is not None:
            self._client.close()
            self._client = None

    # ==================== 基础调用 ====================

    def _call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """调用 MCP 工具并把文本结果解析为字典"""
        import json

        client = self._client_or_none()
        if client is None:
            raise McpError("B站 MCP 服务未启用或不可用")

        text = client.call_tool(tool, arguments)
        if not text:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("MCP 工具 %s 返回非 JSON: %s", tool, text[:200])
            return {"raw": text}
        return data if isinstance(data, dict) else {"items": data}

    def search(self, keyword: str, page_size: int = 20) -> list[dict[str, Any]]:
        """搜索视频，返回原始条目列表"""
        page_size = max(1, min(int(page_size), 50))
        data = self._call(
            "search_bilibili_videos",
            {"keyword": keyword, "page": 1, "ps": page_size},
        )
        items = data.get("items") or data.get("results") or []
        return [item for item in items if isinstance(item, dict)]

    def video_info(self, bvid: str) -> dict[str, Any]:
        """查询单个视频详情（含点赞等互动数据）"""
        return self._call("get_bilibili_video_info", {"bvid": bvid})

    # ==================== 推荐 ====================

    def recommend(self, keyword: str, limit: int = 5) -> dict[str, Any]:
        """
        按关键词推荐视频

        Args:
            keyword: 搜索关键词（动漫作品名或主题）
            limit: 返回条数

        Returns:
            {
              keyword, total, recommendations: [VideoRecommendation dict],
              detail_enriched: int, note: str
            }
        """
        keyword = (keyword or "").strip()
        if not keyword:
            raise McpError("关键词为空")

        limit = max(1, min(int(limit), 10))
        # 多搜一些做候选池：搜索结果的 play 排序不等于综合质量排序
        pool_size = min(max(limit * 4, 20), 50)
        raw_items = self.search(keyword, pool_size)
        if not raw_items:
            return {
                "keyword": keyword,
                "total": 0,
                "recommendations": [],
                "detail_enriched": 0,
                "note": "B站没有搜索到相关视频",
            }

        # 去重（同一 bvid 可能重复出现）
        seen: set[str] = set()
        candidates: list[dict[str, Any]] = []
        for item in raw_items:
            bvid = str(item.get("bvid") or "")
            if not bvid or bvid in seen:
                continue
            seen.add(bvid)
            candidates.append(item)

        # 播放量先排一遍，只在头部候选上补详情，控制 MCP 调用次数
        candidates.sort(key=lambda v: _as_int(_pick(v, "play", "view")), reverse=True)
        detail_limit = max(0, int(self._settings.bilibili_detail_limit))
        enriched = 0
        for item in candidates[:detail_limit]:
            bvid = str(item.get("bvid") or "")
            try:
                detail = self.video_info(bvid)
            except McpError as exc:
                logger.warning("补取视频详情失败 bvid=%s: %s", bvid, exc)
                continue
            if detail and isinstance(detail.get("stat"), dict):
                merged = {**item, **detail}
                candidates[candidates.index(item)] = merged
                enriched += 1

        recommendations = [normalize_video(item) for item in candidates]
        recommendations = [item for item in recommendations if item.title]
        recommendations.sort(key=lambda item: item.score, reverse=True)

        note = ""
        if enriched < min(len(candidates), detail_limit):
            note = "部分视频未能获取点赞等互动数据，排序主要依据播放量"

        return {
            "keyword": keyword,
            "total": len(recommendations),
            "recommendations": [item.to_dict() for item in recommendations[:limit]],
            "detail_enriched": enriched,
            "note": note,
        }


# ==================== 进程级单例 ====================

_service: BilibiliMcpService | None = None


def init_bilibili_service(settings: Settings | None = None) -> BilibiliMcpService:
    """初始化进程级单例"""
    global _service
    if _service is None:
        _service = BilibiliMcpService(settings or get_settings())
    return _service


def get_bilibili_service() -> BilibiliMcpService:
    """获取进程级单例（延迟初始化）"""
    global _service
    if _service is None:
        _service = BilibiliMcpService(get_settings())
    return _service


def shutdown_bilibili_service() -> None:
    """关闭单例（应用退出时调用）"""
    global _service
    if _service is not None:
        _service.close()
        _service = None
