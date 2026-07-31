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
]
