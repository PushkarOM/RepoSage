"""
Retrieval eval cases against RepoSage's own repo (self-referential, but
useful precisely because we know the ground truth exactly). Each case
checks whether at least one expected source file appears among the
top-k chunks returned by search. Includes the two originally parked
observations from earlier in this project as real regression cases.
"""

TEST_CASES = [
    {
        "query": "what is this repo about",
        "expected_sources": ["README.md", "(repository structure)"],
        "note": "originally failed via pure vector search (parked observation, now fixed by multi-query)",
    },
    {
        "query": "check the readme file",
        "expected_sources": ["README.md"],
    },
    {
        "query": "how does the chunker split code differently from documentation",
        "expected_sources": ["chunker.py"],
    },
    {
        "query": "how is conversation memory implemented",
        "expected_sources": ["agent.py"],
    },
    {
        "query": "how does rate limiting work",
        "expected_sources": ["rate_limit.py"],
    },
    {
        "query": "how does reingest avoid running twice at the same time",
        "expected_sources": ["routes.py"],
    },
    {
        "query": "how is the github token used for private repos without exposing it to the LLM",
        "expected_sources": ["tools.py", "context.py"],
    },
    {
        "query": "what is the directory structure of the backend",
        "expected_sources": ["(repository structure)"],
    },
    # --- Tool-coverage cases below ---
    # These cases target tools added in Phase 4 #2 (additional RAG tools).
    # The retrieval eval doesn't invoke tools directly -- it measures
    # whether search_codebase returns the right chunks. Tool selection and
    # tool execution are verified by real chat use, not this harness.
    # Listed here so we have a checklist of "things to ask" when testing
    # the new tools, not because this eval will measure them.
    {
        "query": "when was the chunker last modified",
        "expected_sources": ["backend/app/ingestion/chunker.py"],
        "tool": "list_recent_changes",
    },
    {
        "query": "find tests for the rate limit code",
        "expected_sources": ["tests/test_rate_limit.py"],
        "tool": "find_tests_for",
    },
    {
        "query": "where is the search_codebase tool defined",
        "expected_sources": ["tools.py"],
        "tool": "find_definition",
    },
    {
        "query": "show me lines 10 to 25 of backend/app/agent/agent.py",
        "expected_sources": ["agent.py"],
        "tool": "read_file_section",
    },
    # --- Entity-conflation dedup (Phase 4 #4) ---
    # Not directly measurable by the retrieval eval: this is a chunker
    # invariant, not a retrieval property. The post-dedup chunk count
    # for RepoSage's README should be lower than the pre-dedup count.
    # Verification: re-ingest and compare the per-source chunk counts
    # in the eval artifact before and after the dedup landed.
    {
        "query": "dedup invariant: README.md chunks should not contain near-duplicate paragraphs",
        "expected_sources": ["README.md"],
        "invariant": "dedupe_chunks",
    },
]
