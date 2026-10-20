"""
动漫相关性前置过滤

逻辑自重构前的 anime_agent.py 原样迁移，行为完全一致：
命中关键词、含数字的"我/用户"问句、问候语、或长度不足 10 字符时放行。
"""

# 动漫相关关键词
ANIME_KEYWORDS = [
    "动漫", "动画", "番剧", "新番", "追番", "看番",
    "anime", "animation", "cartoon",
    "角色", "剧情", "结局", "推荐", "评分", "评价",
    "漫画", "轻小说", "二次元", "ACG",
    "观看", "追剧", "完结", "更新", "集数",
    "类型", "题材", "制作公司", "声优", "配音",
    "喜欢", "讨厌", "最爱", "排行", "统计",
]

# 问候语
GREETINGS = ["你好", "hello", "hi", "hey", "早上好", "晚上好", "下午好"]

# 短问题放行阈值
SHORT_QUESTION_LENGTH = 10


def is_anime_related_question(question: str) -> bool:
    """
    简单判断问题是否与动漫相关（前置过滤）

    Args:
        question: 用户问题

    Returns:
        bool: 是否可能是动漫相关问题
    """
    if not question:
        return False

    question_lower = question.lower()

    # 检查是否包含动漫相关关键词
    for keyword in ANIME_KEYWORDS:
        if keyword in question_lower:
            return True

    # 如果问题中包含数字且提到用户，可能是查询个人数据
    if ("用户" in question or "我" in question) and any(
        char.isdigit() for char in question
    ):
        return True

    # 允许简单的问候语（让AI来判断）
    for greeting in GREETINGS:
        if greeting in question_lower:
            return True

    # 如果问题很短（少于10个字符），也允许通过（让AI判断）
    if len(question) < SHORT_QUESTION_LENGTH:
        return True

    return False
