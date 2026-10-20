"""
知识文件摄取

完整流程：保存原文件 → 解析文本 → 分块 → 向量化 → 写入 Chroma。

原文件会落盘到 `knowledge_dir`（默认 ai/knowledge），便于溯源与重新索引；
返回给前端的只有文件名等非敏感信息。
"""

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.rag.loaders import (
    DocumentParseError,
    UnsupportedFileTypeError,
    extract_text,
    split_text,
)
from app.rag.store import KnowledgeStore

logger = logging.getLogger(__name__)

# 文件名安全字符（去掉路径分隔符与特殊字符，防止目录穿越）
_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@dataclass
class IngestResult:
    """一次摄取的结果"""

    filename: str
    chars: int
    chunks: int
    stored: int
    elapsed_ms: int
    embedding_provider: str
    semantic: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "chars": self.chars,
            "chunks": self.chunks,
            "stored": self.stored,
            "elapsedMs": self.elapsed_ms,
            "embeddingProvider": self.embedding_provider,
            "semantic": self.semantic,
        }


def sanitize_filename(filename: str) -> str:
    """
    规整上传文件名

    仅保留基础名并替换不安全字符，避免路径穿越（如 ../../etc/passwd）。
    """
    base = os.path.basename(filename or "").strip()
    base = _UNSAFE_CHARS.sub("_", base)
    base = base.lstrip(".") or "unnamed"
    return base[:120]


class KnowledgeIngestService:
    """知识文件摄取服务"""

    def __init__(self, settings: Settings, store: KnowledgeStore) -> None:
        self._settings = settings
        self._store = store

    @property
    def store(self) -> KnowledgeStore:
        return self._store

    def ingest(self, filename: str, raw: bytes) -> IngestResult:
        """
        摄取一个知识文件

        Args:
            filename: 原始文件名
            raw: 文件字节内容

        Returns:
            摄取结果

        Raises:
            UnsupportedFileTypeError / DocumentParseError: 校验或解析失败
        """
        started = time.time()
        safe_name = sanitize_filename(filename)

        # 1) 解析文本（含大小与类型校验，大小上限走配置）
        max_size = self._settings.rag_max_file_size_mb * 1024 * 1024
        text = extract_text(safe_name, raw, max_size=max_size)
        logger.info("已解析知识文件: file=%s, 字符数=%d", safe_name, len(text))

        # 2) 分块
        chunks = split_text(
            text,
            source=safe_name,
            chunk_size=self._settings.rag_chunk_size,
            overlap=self._settings.rag_chunk_overlap,
        )
        if not chunks:
            raise DocumentParseError("文件内容无法切分出有效文本块")

        # 3) 原文件落盘（失败不阻断入库，仅记录）
        self._save_original(safe_name, raw)

        # 4) 向量化并入向量库（内部会先清除同文件的旧块）
        stored = self._store.add_chunks(safe_name, raw, chunks)

        elapsed_ms = int((time.time() - started) * 1000)
        logger.info(
            "知识文件摄取完成: file=%s, 块=%d, 耗时=%dms", safe_name, stored, elapsed_ms
        )

        return IngestResult(
            filename=safe_name,
            chars=len(text),
            chunks=len(chunks),
            stored=stored,
            elapsed_ms=elapsed_ms,
            embedding_provider=self._store.embeddings.name,
            semantic=self._store.embeddings.semantic,
        )

    def _save_original(self, safe_name: str, raw: bytes) -> None:
        """把原文件保存到 knowledge 目录（同名覆盖）"""
        try:
            directory = self._settings.knowledge_dir
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, safe_name)
            with open(path, "wb") as handle:
                handle.write(raw)
            logger.debug("原文件已保存: %s", path)
        except OSError as exc:
            logger.warning("保存原文件失败（不影响入库）: %s", exc)

    # ==================== 查询与删除 ====================

    def list_sources(self) -> list[dict[str, Any]]:
        """列出已入库文件"""
        return self._store.list_sources()

    def delete_source(self, filename: str) -> int:
        """删除某个文件的知识（同时删除落盘原文件）"""
        safe_name = sanitize_filename(filename)
        removed = self._store.delete_by_source(safe_name)

        path = os.path.join(self._settings.knowledge_dir, safe_name)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError as exc:
            logger.warning("删除原文件失败: %s", exc)

        return removed

    def total_chunks(self) -> int:
        """块总数"""
        return self._store.count()


__all__ = [
    "IngestResult",
    "KnowledgeIngestService",
    "DocumentParseError",
    "UnsupportedFileTypeError",
    "sanitize_filename",
]
