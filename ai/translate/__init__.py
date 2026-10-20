"""
翻译模块
提供动漫名称翻译功能
"""

from translate.translate_anime_titles import (
    get_db_connection,
    translate_with_deepseek,
    get_anime_list,
    update_anime_title,
    is_chinese,
    main
)

__all__ = [
    'get_db_connection',
    'translate_with_deepseek',
    'get_anime_list',
    'update_anime_title',
    'is_chinese',
    'main'
]
