"""
RAG（检索增强生成）模块

组成：
    embeddings.py  Embedding 提供方（DashScope / 本地兜底）
    loaders.py     文档解析（txt / md / pdf）与分块
    store.py       Chroma 向量库（写入 / 检索 / 删除）
    ingest.py      知识文件摄取编排
    tools.py       Agent 可调用的知识库检索工具

数据落盘：
    chroma_persist_dir  向量库（默认 ai/chroma_db）
    knowledge_dir       上传的原始文件（默认 ai/knowledge）
"""

from app.rag.embeddings import BaseEmbeddings, build_embeddings
from app.rag.ingest import (
    IngestResult,
    KnowledgeIngestService,
    sanitize_filename,
)
from app.rag.loaders import (
    SUPPORTED_EXTENSIONS,
    DocumentParseError,
    UnsupportedFileTypeError,
)
from app.rag.store import (
    KnowledgeStore,
    SearchHit,
    get_knowledge_store,
    init_knowledge_store,
)

__all__ = [
    "BaseEmbeddings",
    "DocumentParseError",
    "IngestResult",
    "KnowledgeIngestService",
    "KnowledgeStore",
    "SUPPORTED_EXTENSIONS",
    "SearchHit",
    "UnsupportedFileTypeError",
    "build_embeddings",
    "get_knowledge_store",
    "init_knowledge_store",
    "sanitize_filename",
]
