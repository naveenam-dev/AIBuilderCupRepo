"""Reciprocal Rank Fusion (Cormack et al., 2009): score = sum over rankings of 1 / (k + rank)."""


def rrf(rankings: dict[str, list[str]], k: int = 60) -> list[tuple[str, float, dict[str, int]]]:
    """`rankings` maps a ranker name to an ordered list of ids (best first, 1-based ranks).
    Returns (id, fused_score, {ranker: rank}) sorted by fused score."""
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for name, ids in rankings.items():
        for rank, item in enumerate(ids, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
            ranks.setdefault(item, {})[name] = rank
    ordered = sorted(scores, key=scores.__getitem__, reverse=True)
    return [(i, scores[i], ranks[i]) for i in ordered]
