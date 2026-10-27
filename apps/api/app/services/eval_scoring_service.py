"""Eval scoring — Hit@k / keywords (KB_PRIVATE_DELIVERY_SPEC §4.2)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.models.eval import EvalCase
from app.rag.retrieval_orchestrator import NormalizedHit


def _norm_ids(raw: Optional[list]) -> List[str]:
    if not raw:
        return []
    return [str(x) for x in raw if x]


def score_case(case: EvalCase, hits: List[NormalizedHit]) -> Tuple[bool, str]:
    """Return (pass, reason_code)."""
    if not hits:
        if _norm_ids(case.expected_chunk_ids) or _norm_ids(case.expected_document_ids):
            return False, "empty"
        if case.expected_keywords:
            return False, "empty"
        return True, "ok"

    chunk_ids = [str(h.chunk_id) for h in hits if h.chunk_id]
    doc_ids = [str(h.document_id) for h in hits if h.document_id]
    merged_text = " ".join((h.content or "") for h in hits).lower()

    for bad in _norm_ids(case.must_not_keywords):
        if bad.lower() in merged_text:
            return False, "must_not_keyword"

    hit_ok = False
    exp_chunks = _norm_ids(case.expected_chunk_ids)
    exp_docs = _norm_ids(case.expected_document_ids)
    if exp_chunks:
        hit_ok = any(cid in chunk_ids for cid in exp_chunks)
    elif exp_docs:
        hit_ok = any(did in doc_ids for did in exp_docs)
    else:
        hit_ok = True

    if not hit_ok:
        return False, "miss_hit"

    for kw in _norm_ids(case.expected_keywords):
        if kw.lower() not in merged_text:
            return False, "miss_keyword"

    return True, "ok"


def aggregate_metrics(
    per_case: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total = len(per_case)
    if total == 0:
        return {
            "total": 0,
            "passed": 0,
            "hit_at_k_rate": 0.0,
            "empty_rate": 0.0,
            "latency_ms_p50": 0,
            "latency_ms_p95": 0,
        }
    passed = sum(1 for r in per_case if r.get("pass"))
    empty = sum(1 for r in per_case if r.get("reason") == "empty")
    latencies = sorted(r.get("latency_ms") or 0 for r in per_case)
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)]
    return {
        "total": total,
        "passed": passed,
        "hit_at_k_rate": round(passed / total, 4),
        "empty_rate": round(empty / total, 4),
        "latency_ms_p50": p50,
        "latency_ms_p95": p95,
    }
