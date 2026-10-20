"""
统一响应契约模块

严格保持与重构前 Flask 版本完全一致的响应体结构：

成功: {"success": true, "message": "...", "timestamp": <float>, "data"?: {...}}
失败: {"success": false, "error": {"message": "...", "code": "...", "timestamp": <float>, "data"?: {...}}}
"""

import time
from typing import Any


def success_response(data: Any = None, message: str = "操作成功") -> dict:
    """
    构造统一成功响应

    Args:
        data: 响应数据，为 None 时不输出 data 字段
        message: 成功消息

    Returns:
        符合契约的响应字典
    """
    response: dict[str, Any] = {
        "success": True,
        "message": message,
        "timestamp": time.time(),
    }

    if data is not None:
        response["data"] = data

    return response


def error_response(
    message: str,
    error_code: str = "INVALID_REQUEST",
    extra_data: Any = None,
) -> dict:
    """
    构造统一错误响应

    Args:
        message: 错误消息
        error_code: 错误代码（前端 mapErrorCode 依赖此字符串）
        extra_data: 附加在 error.data 下的额外信息

    Returns:
        符合契约的响应字典
    """
    error: dict[str, Any] = {
        "message": message,
        "code": error_code,
        "timestamp": time.time(),
    }

    if extra_data is not None:
        error["data"] = extra_data

    return {"success": False, "error": error}
