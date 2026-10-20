"""
知识文档加载与分块

支持格式：
- 纯文本：.txt / .md / .markdown（自动尝试多种编码）
- PDF：.pdf（依赖 pypdf）

分块策略：按段落聚合到目标长度，超长段落再按句子边界切分，
块之间保留重叠，避免关键信息正好落在切口上。
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 允许上传的扩展名（MIME 在浏览器侧常不准确，因此以扩展名为准）
SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf"}

# 单次上传大小上限（字节）—— 实际以 settings.rag_max_file_size_mb 为准，
# 这里的常量仅作为未走配置时的兜底
DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_FILE_SIZE = DEFAULT_MAX_FILE_SIZE

# 分块参数（默认值，实际以 settings.rag_chunk_size / rag_chunk_overlap 为准）
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 80

# 文本编码尝试顺序（中文环境常见）
_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030", "big5", "latin-1")


class UnsupportedFileTypeError(ValueError):
    """不支持的文件类型"""


class DocumentParseError(ValueError):
    """文件解析失败（如损坏的 PDF）"""


@dataclass
class TextChunk:
    """一个待向量化的文本块"""

    content: str
    index: int
    source: str
    # 块在原文中的大致位置（字符偏移），便于溯源
    offset: int = 0


def _decode_text(raw: bytes) -> str:
    """按候选编码解码文本，全部失败时用 utf-8 忽略错误兜底"""
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    logger.warning("文本编码识别失败，使用 utf-8 忽略错误解码")
    return raw.decode("utf-8", errors="ignore")


def _extract_pdf(raw: bytes) -> str:
    """用 pypdf 提取 PDF 文本"""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - 依赖缺失时的明确提示
        raise DocumentParseError("未安装 pypdf，无法解析 PDF") from exc

    import io

    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            # 尝试空密码解密（部分 PDF 只是设置了权限位）
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                raise DocumentParseError("PDF 已加密，无法解析")

        pages: list[str] = []
        for number, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001 - 单页失败不影响其它页
                logger.warning("PDF 第 %d 页解析失败: %s", number, exc)
                continue
            if text.strip():
                pages.append(text)
    except DocumentParseError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DocumentParseError(f"PDF 解析失败: {exc}") from exc

    if not pages:
        raise DocumentParseError(
            "PDF 中未提取到文本（可能是扫描件/纯图片，需要 OCR 才能处理）"
        )

    return "\n\n".join(pages)


def extract_text(filename: str, raw: bytes, max_size: int | None = None) -> str:
    """
    从上传文件中提取纯文本

    Args:
        filename: 原始文件名（用于判断类型）
        raw: 文件字节内容
        max_size: 大小上限（字节），缺省用 DEFAULT_MAX_FILE_SIZE

    Returns:
        提取到的文本

    Raises:
        UnsupportedFileTypeError: 扩展名不支持
        DocumentParseError: 解析失败或内容为空
    """
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"不支持的文件类型 {suffix or '(无扩展名)'}，"
            f"仅支持 {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    limit = max_size or DEFAULT_MAX_FILE_SIZE
    if len(raw) > limit:
        raise DocumentParseError(
            f"文件过大（{len(raw) / 1024 / 1024:.1f}MB），上限 {limit // 1024 // 1024}MB"
        )

    text = _extract_pdf(raw) if suffix == ".pdf" else _decode_text(raw)

    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise DocumentParseError("文件内容为空")

    return text


def _split_long_paragraph(paragraph: str, chunk_size: int, overlap: int) -> list[str]:
    """超长段落按句子边界切分"""
    # 先按中英文句末标点切句
    sentences: list[str] = []
    buffer = ""
    for char in paragraph:
        buffer += char
        if char in "。！？!?；;\n":
            sentences.append(buffer)
            buffer = ""
    if buffer.strip():
        sentences.append(buffer)

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= chunk_size:
            current += sentence
            continue

        if current.strip():
            chunks.append(current.strip())
        # 单句本身就超长时硬切
        if len(sentence) > chunk_size:
            for start in range(0, len(sentence), chunk_size - overlap):
                piece = sentence[start : start + chunk_size].strip()
                if piece:
                    chunks.append(piece)
            current = ""
        else:
            # 保留重叠：把上一块尾部拼到新块开头
            tail = current[-overlap:] if overlap and current else ""
            current = tail + sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks


def split_text(
    text: str,
    source: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    """
    把长文本切分为带重叠的块

    先按空行分段，再把段落聚合到接近 chunk_size，超长段落单独切分。

    Args:
        text: 原文
        source: 来源标识（文件名）
        chunk_size: 目标块长度（字符）
        overlap: 块间重叠长度（字符）

    Returns:
        文本块列表
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须为正数")
    overlap = max(0, min(overlap, chunk_size // 2))

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    raw_chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current.strip():
                raw_chunks.append(current.strip())
                current = ""
            raw_chunks.extend(_split_long_paragraph(paragraph, chunk_size, overlap))
            continue

        if len(current) + len(paragraph) + 2 <= chunk_size:
            current = f"{current}\n\n{paragraph}" if current else paragraph
        else:
            if current.strip():
                raw_chunks.append(current.strip())
            tail = current[-overlap:] if overlap and current else ""
            current = f"{tail}\n\n{paragraph}" if tail else paragraph

    if current.strip():
        raw_chunks.append(current.strip())

    # 计算偏移用于溯源
    chunks: list[TextChunk] = []
    cursor = 0
    for index, content in enumerate(raw_chunks):
        offset = text.find(content[:40], cursor) if content else -1
        if offset < 0:
            offset = cursor
        cursor = offset + len(content)
        chunks.append(TextChunk(content=content, index=index, source=source, offset=offset))

    return chunks
