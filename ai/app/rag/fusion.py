"""
多路检索结果融合：RRF（Reciprocal Rank Fusion）

为什么手写：LangChain 原本用 `EnsembleRetriever` 做这件事，但它在
langchain 1.x 中已被移除（实测 `from langchain.retrievers import EnsembleRetriever`
报 ModuleNotFoundError），community 包里也没有替代品。而 RRF 本身只有十来行，
所以就地实现。

RRF 的好处是**不需要对齐两路分数的尺度**：向量相似度是 0-1 的余弦相似度，
BM25 是无上界的加权词频分，两者直接相加没有意义。RRF 只看**名次**：

    score(d) = Σ_r  weight_r / (k + rank_r(d))

k 通常取 60（原论文经验值），作用是压低头部名次的差距，让多路都靠前的
文档胜出，而不是被某一路的第一名垄断。
"""


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    weights: list[float] | None = None,
    k: int = 60,
) -> list[tuple[str, float]]:
    """
    融合多路检索结果

    Args:
        rankings: 多路检索结果，每路是按相关度降序排列的文档 key 列表
        weights: 每路权重（缺省等权）
        k: RRF 平滑常数，默认 60

    Returns:
        [(key, score), ...]，按融合分降序（同分时保持首次出现的顺序）
    """
    if not rankings:
        return []

    if weights is None:
        weights = [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError("weights 数量必须与 rankings 一致")

    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    counter = 0

    for ranking, weight in zip(rankings, weights):
        if not weight:
            continue
        for rank, key in enumerate(ranking, start=1):
            if not key:
                continue
            scores[key] = scores.get(key, 0.0) + weight / (k + rank)
            if key not in first_seen:
                first_seen[key] = counter
                counter += 1

    ordered = sorted(
        scores.items(),
        key=lambda item: (-item[1], first_seen.get(item[0], 0)),
    )
    return ordered


def normalize_scores(items: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """
    把 RRF 分数线性归一化到 0-1（仅供展示）

    RRF 分数绝对值很小（k=60 时第一名约 1/61≈0.016），直接当相似度展示
    没有可读性；归一化后第一名接近 1.0。
    """
    if not items:
        return []
    top = max(score for _, score in items)
    if top <= 0:
        return [(key, 0.0) for key, _ in items]
    return [(key, score / top) for key, score in items]
