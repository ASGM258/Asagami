"""
知识库接口（RAG）

    POST   /api/knowledge/upload    上传知识文件（txt / md / pdf）
    GET    /api/knowledge/files     已入库文件列表
    DELETE /api/knowledge/files     删除某个文件的知识
    GET    /api/knowledge/stats     知识库统计

响应体沿用本服务统一外壳：{success, message, timestamp, data}
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile

from app.config import get_settings
from app.core.errors import BusinessError
from app.core.responses import success_response
from app.dependencies import get_knowledge_service
from app.rag.ingest import (
    DocumentParseError,
    KnowledgeIngestService,
    UnsupportedFileTypeError,
)
from app.rag.loaders import SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


@router.post("/upload", summary="上传知识文件")
async def upload_knowledge(
    file: UploadFile = File(..., description="知识文件（txt / md / pdf）"),
    service: KnowledgeIngestService = Depends(get_knowledge_service),
):
    """
    上传知识文件并建立索引

    流程：解析文本 → 分块 → 向量化 → 写入 Chroma。
    同一文件重复上传会覆盖旧内容（按文件名 + 内容指纹去重）。
    """
    filename = file.filename or "unnamed"

    settings = get_settings()
    max_size = settings.rag_max_file_size_mb * 1024 * 1024

    raw = await file.read()
    if not raw:
        raise BusinessError(
            message="上传的文件为空", error_code="EMPTY_FILE", http_status=400
        )

    if len(raw) > max_size:
        raise BusinessError(
            message=(
                f"文件过大（{len(raw) / 1024 / 1024:.1f}MB），"
                f"上限 {settings.rag_max_file_size_mb}MB"
            ),
            error_code="FILE_TOO_LARGE",
            http_status=413,
        )

    try:
        # 摄取是 CPU/IO 密集型（解析 + 向量化），放线程池避免阻塞事件循环
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(service.ingest, filename, raw)
    except UnsupportedFileTypeError as exc:
        raise BusinessError(
            message=str(exc), error_code="UNSUPPORTED_FILE_TYPE", http_status=400
        ) from exc
    except DocumentParseError as exc:
        raise BusinessError(
            message=str(exc), error_code="DOCUMENT_PARSE_FAILED", http_status=400
        ) from exc
    except Exception as exc:  # noqa: BLE001 - 向量化失败（如未配置密钥）
        logger.exception("知识文件摄取失败: %s", exc)
        raise BusinessError(
            message=f"建立索引失败: {exc}",
            error_code="INGEST_FAILED",
            http_status=500,
        ) from exc

    return success_response(
        data=result.to_dict(), message=f"「{result.filename}」已加入知识库"
    )


@router.get("/files", summary="已入库文件列表")
async def list_knowledge_files(
    service: KnowledgeIngestService = Depends(get_knowledge_service),
):
    """列出已入库的知识文件及其块数"""
    from starlette.concurrency import run_in_threadpool

    files = await run_in_threadpool(service.list_sources)

    data: dict[str, Any] = {
        "files": files,
        "count": len(files),
        "totalChunks": await run_in_threadpool(service.total_chunks),
        "embeddingProvider": service.store.embeddings.name,
        "semantic": service.store.embeddings.semantic,
        "supportedExtensions": sorted(SUPPORTED_EXTENSIONS),
    }
    return success_response(data=data, message="获取知识库文件成功")


@router.delete("/files", summary="删除知识文件")
async def delete_knowledge_file(
    filename: str,
    service: KnowledgeIngestService = Depends(get_knowledge_service),
):
    """按文件名删除知识（同时删除落盘的原文件）"""
    from starlette.concurrency import run_in_threadpool

    if not filename.strip():
        raise BusinessError(
            message="缺少必要参数：filename",
            error_code="MISSING_PARAMETER",
            http_status=400,
        )

    removed = await run_in_threadpool(service.delete_source, filename)

    if removed == 0:
        raise BusinessError(
            message=f"知识库中不存在「{filename}」",
            error_code="KNOWLEDGE_NOT_FOUND",
            http_status=404,
        )

    return success_response(
        data={"filename": filename, "removedChunks": removed},
        message=f"已删除「{filename}」",
    )


@router.get("/stats", summary="知识库统计")
async def knowledge_stats(
    service: KnowledgeIngestService = Depends(get_knowledge_service),
):
    """知识库概览：文件数、块数、当前 embedding 提供方"""
    settings = get_settings()

    from starlette.concurrency import run_in_threadpool

    files = await run_in_threadpool(service.list_sources)
    total = await run_in_threadpool(service.total_chunks)

    return success_response(
        data={
            "fileCount": len(files),
            "totalChunks": total,
            "embeddingProvider": service.store.embeddings.name,
            "semantic": service.store.embeddings.semantic,
            "chunkSize": settings.rag_chunk_size,
            "chunkOverlap": settings.rag_chunk_overlap,
            "maxFileSizeMb": settings.rag_max_file_size_mb,
        },
        message="获取知识库统计成功",
    )
