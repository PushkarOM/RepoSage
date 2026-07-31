"""
Offline retrieval eval. Run manually against an already-ingested repo:

    python -m eval.run_eval <repo_id>

Not part of pytest/CI -- needs live Chroma data and a real LLM call
(multi-query expansion), and measures a quality score that can drift
slightly run to run, not a strict pass/fail gate.
"""
import asyncio
import sys
from app.ingestion.vectorstore import multi_search
from eval.test_cases import TEST_CASES


async def run(repo_id: str):
    passed = 0
    print(f"Running {len(TEST_CASES)} retrieval eval cases against repo_id={repo_id}\n")

    for case in TEST_CASES:
        results = await multi_search(case["query"], k=5, repo_id=repo_id)
        retrieved_sources = {r.metadata.get("source", "") for r in results}

        hit = any(
            any(expected in src for src in retrieved_sources)
            for expected in case["expected_sources"]
        )
        
        status = "PASS" if hit else "FAIL"
        if hit:
            passed += 1

        print(f"[{status}] {case['query']}")
        print(f"       expected one of: {case['expected_sources']}")
        print(f"       got sources: {sorted(retrieved_sources)}")
        if note := case.get("note"):
            print(f"       note: {note}")
        print()

    score = passed / len(TEST_CASES) * 100
    print(f"--- {passed}/{len(TEST_CASES)} passed ({score:.0f}%) ---")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m eval.run_eval <repo_id>")
        sys.exit(1)
    asyncio.run(run(sys.argv[1]))
