"""
Offline retrieval eval. Run manually against an already-ingested repo:

    python -m eval.run_eval <repo_id>

Not part of pytest/CI -- needs live Chroma data and a real LLM call
(multi-query expansion), and measures a quality score that can drift
slightly run to run, not a strict pass/fail gate.

Compares multiple retrievers side by side so we can see the impact of
each Phase 4 change (hybrid search, entity dedup, new tools) on the
same benchmark rather than eyeballing one query at a time.
"""
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.ingestion.vectorstore import multi_search, search, hybrid_search
from eval.test_cases import TEST_CASES


# Latency guardrail. Hybrid search builds/queries an in-memory BM25 index
# on every call (no persistent store for the keyword side), so the budget
# exists specifically to catch a regression where this number balloons.
# Soft warn -- not a hard fail -- because the LLM expansion in multi_query
# legitimately adds 100-300ms that isn't a retriever-quality issue.
LATENCY_BUDGET_MS = 1500

# JSON artifact for cross-session score tracking. Lives next to the eval
# code, gitignored -- this is a convenience for the developer, not a
# shipped artifact or part of any user-facing surface.
ARTIFACT_PATH = Path(__file__).parent / "last_run.json"


async def _async_search(query: str, k: int, repo_id: str):
    # Plain vector search is sync -- wrap so the dict of retrievers can
    # be uniform without every caller needing to know which is which.
    return search(query, k=k, repo_id=repo_id)


async def _multi_query(query: str, k: int, repo_id: str):
    return await multi_search(query, k=k, repo_id=repo_id)


async def _hybrid_search(query: str, k: int, repo_id: str):
    return await hybrid_search(query, k=k, repo_id=repo_id)


# Each retriever: name -> async fn(query, k, repo_id) -> list[Document]
# Defined here rather than imported so the eval stays self-contained and
# trivially extensible (add a new retriever = add one entry to the dict).
RETRIEVERS: dict[str, Callable] = {
    # Pure vector similarity -- the original baseline. Helps quantify what
    # multi-query expansion alone buys us.
    "vector_only": _async_search,

    # Current production retriever: LLM-expanded multi-query, deduped.
    "multi_query": _multi_query,

    # Phase 4 hybrid: BM25 + vector, fused via reciprocal rank fusion,
    # with cheap routing that skips BM25 on exact-path / short-identifier
    # queries to keep the fast path fast.
    "hybrid": _hybrid_search,
}


async def _score_retriever(name: str, retriever: Callable, repo_id: str) -> dict:
    """
    Runs every test case through one retriever and returns aggregate
    metrics. Per-case detail is also kept so the printed report can show
    which queries are hardest, not just the average.
    """
    mrr_sum = 0.0
    recall_hits = 0
    latencies = []
    per_case = []

    for case in TEST_CASES:
        start = time.perf_counter()
        results = await retriever(case["query"], 5, repo_id)
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)

        retrieved_sources = [r.metadata.get("source", "") for r in results]
        # Reciprocal rank of the FIRST hit against any expected source.
        # 0.0 if no hit at all, otherwise 1/(position+1) so 1.0 = top result.
        rr = 0.0
        for i, src in enumerate(retrieved_sources):
            if any(expected in src for expected in case["expected_sources"]):
                rr = 1.0 / (i + 1)
                break
        mrr_sum += rr
        if rr > 0:
            recall_hits += 1

        per_case.append({
            "query": case["query"],
            "rr": round(rr, 4),
            "got": retrieved_sources,
            "expected": case["expected_sources"],
            "elapsed_ms": int(elapsed * 1000),
        })

    return {
        "name": name,
        "mrr": round(mrr_sum / len(TEST_CASES), 4),
        "recall_at_5": round(recall_hits / len(TEST_CASES), 4),
        "avg_latency_ms": int(sum(latencies) / len(latencies) * 1000),
        "per_case": per_case,
    }


def _print_report(scores: list[dict]) -> None:
    print(f"\n{'='*72}")
    print("RETRIEVAL EVAL -- per-retriever comparison")
    print(f"{'='*72}\n")

    # Summary table first -- the headline number for "did Phase 4 work?"
    header = f"{'retriever':<16} {'MRR':>6} {'R@5':>6} {'avg ms':>8} {'budget':>8}"
    print(header)
    print("-" * len(header))
    for s in scores:
        # Latency budget is per-retriever, not a hard fail. We surface it
        # so a slow retriever is obvious at a glance, not a silent tax.
        over = "OVER " if s["avg_latency_ms"] > LATENCY_BUDGET_MS else "ok"
        print(
            f"{s['name']:<16} {s['mrr']:>6.3f} {s['recall_at_5']:>6.1%} "
            f"{s['avg_latency_ms']:>8} {over:>8}"
        )
    print()

    # Per-case detail so it's easy to spot which queries are still hard
    # and which retriever helps them most.
    for s in scores:
        print(f"--- {s['name']} ---")
        for c in s["per_case"]:
            mark = "OK  " if c["rr"] > 0 else "MISS"
            print(f"  [{mark}] rr={c['rr']:.2f} ({c['elapsed_ms']}ms)  {c['query']}")
            if c["rr"] == 0:
                print(f"        expected one of: {c['expected']}")
                print(f"        got:             {c['got']}")
        print()


def _write_artifact(repo_id: str, scores: list[dict]) -> None:
    """
    Persists the latest run so scores survive across sessions -- the next
    time we run the eval we can diff against this without git archaeology.
    Overwrites unconditionally; the file is a snapshot of "last run", not
    a history (history would belong in git notes or a real DB, not here).
    """
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo_id": repo_id,
        "num_cases": len(TEST_CASES),
        "latency_budget_ms": LATENCY_BUDGET_MS,
        "retrievers": {
            s["name"]: {
                "mrr": s["mrr"],
                "recall_at_5": s["recall_at_5"],
                "avg_latency_ms": s["avg_latency_ms"],
                "over_budget": s["avg_latency_ms"] > LATENCY_BUDGET_MS,
                "per_case": s["per_case"],
            }
            for s in scores
        },
    }
    # write_text isn't atomic on Windows (no rename() atomicity guarantee
    # for the same path) but this is a dev-only artifact -- if a partial
    # write happens, the next run overwrites it. Not worth a tempfile dance.
    ARTIFACT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\nArtifact written: {ARTIFACT_PATH}")


WARMUP_QUERY = "warmup query for embedding model load"


async def _warmup(retrievers: dict[str, Callable], repo_id: str) -> None:
    """
    Pre-runs every retriever once on a throwaway query so the first
    real measurement isn't polluted by cold-start costs (embedding model
    load ~15s, BM25 index build ~50ms, LLM call in multi_query ~1s).
    The warmup results are discarded; only the steady-state numbers
    end up in the eval report. Without this, vector_only looks ~60x
    slower than hybrid just because the first query paid the warmup tax.
    """
    for name, retriever in retrievers.items():
        try:
            await retriever(WARMUP_QUERY, 1, repo_id)
        except Exception:
            # Warmup failures shouldn't kill the eval. If a retriever
            # genuinely can't run a throwaway query, the timed run will
            # surface that.
            pass


async def run(repo_id: str) -> None:
    print(f"Running {len(TEST_CASES)} eval cases against repo_id={repo_id}\n")
    print("Warming up retrievers (cold-start costs discarded)...", end="", flush=True)
    await _warmup(RETRIEVERS, repo_id)
    print(" done.\n")
    scores = []
    for name, retriever in RETRIEVERS.items():
        print(f"  running {name}...", end="", flush=True)
        s = await _score_retriever(name, retriever, repo_id)
        print(f"  mrr={s['mrr']:.3f} r@5={s['recall_at_5']:.1%} {s['avg_latency_ms']}ms")
        scores.append(s)
    _print_report(scores)
    _write_artifact(repo_id, scores)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m eval.run_eval <repo_id>")
        sys.exit(1)
    asyncio.run(run(sys.argv[1]))
