"""Ranking metrics for labelled retrieval cases."""

from __future__ import annotations

import math


def evaluate_retrieval(retrieved: list[str], relevant: list[str], k: int = 10) -> dict[str, float]:
    ranked = retrieved[:k]
    relevant_set = set(relevant)
    hits = [item for item in ranked if item in relevant_set]
    precision = len(hits) / len(ranked) if ranked else 0.0
    recall = len(set(hits)) / len(relevant_set) if relevant_set else 1.0
    reciprocal_rank = next((1.0 / (index + 1) for index, item in enumerate(ranked) if item in relevant_set), 0.0)
    dcg = sum(1.0 / math.log2(index + 2) for index, item in enumerate(ranked) if item in relevant_set)
    ideal = sum(1.0 / math.log2(index + 2) for index in range(min(k, len(relevant_set))))
    return {"precision_at_k": precision, "recall_at_k": recall, "mrr": reciprocal_rank, "ndcg": dcg / ideal if ideal else 0.0}
