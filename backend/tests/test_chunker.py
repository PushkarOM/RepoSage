from pathlib import Path
from langchain_core.documents import Document

from app.ingestion.chunker import load_and_chunk, _dedupe_chunks


def make_fake_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "node_modules").mkdir()

    (tmp_path / "src" / "main.py").write_text(
        "def add(a, b):\n    return a + b\n"
    )
    (tmp_path / "docs" / "README.md").write_text(
        "# Fake repo\nA tiny repo for testing.\n"
    )
    (tmp_path / "src" / "data.bin").write_bytes(bytes(range(256)))
    (tmp_path / "node_modules" / "ignored.js").write_text("console.log('ignore me')")

    return tmp_path


def test_chunker_produces_code_and_doc_chunks(tmp_path):
    repo = make_fake_repo(tmp_path)
    docs = load_and_chunk(repo)

    code_chunks = [d for d in docs if d.metadata["type"] == "code"]
    doc_chunks = [d for d in docs if d.metadata["type"] == "doc"]

    assert len(code_chunks) > 0
    assert len(doc_chunks) > 0


def test_chunker_skips_binary_files(tmp_path):
    repo = make_fake_repo(tmp_path)
    docs = load_and_chunk(repo)

    sources = [d.metadata["source"] for d in docs]
    assert not any("data.bin" in s for s in sources)


def test_chunker_skips_ignored_directories(tmp_path):
    repo = make_fake_repo(tmp_path)
    docs = load_and_chunk(repo)

    sources = [d.metadata["source"] for d in docs]
    assert not any("node_modules" in s for s in sources)


def test_chunker_uses_relative_paths(tmp_path):
    repo = make_fake_repo(tmp_path)
    docs = load_and_chunk(repo)

    for d in docs:
        assert not d.metadata["source"].startswith(str(tmp_path))


# --- _dedupe_chunks tests (Phase 4 #4: entity-conflation fix) ---

def _mk_doc(text: str, idx: int = 0) -> Document:
    return Document(page_content=text, metadata={"source": "test.md", "chunk_index": idx})


def test_dedupe_drops_near_duplicate_chunks():
    # Two chunks with the same 5-shingles (identical paragraph in two
    # sections). The second should be dropped.
    para = (
        "Project Foo is a small library that helps with text processing. "
        "It supports tokenization, stemming, and lemmatization out of the box. "
        "It's used by several internal tools and has a stable public API."
    )
    docs = [_mk_doc(para, 0), _mk_doc(para, 1)]
    kept = _dedupe_chunks(docs)
    assert len(kept) == 1
    assert kept[0].metadata["chunk_index"] == 0  # first copy survives


def test_dedupe_keeps_unrelated_chunks():
    a = "The quick brown fox jumps over the lazy dog in the morning light."
    b = "Database migrations are run automatically on application startup."
    c = "Logger configuration lives in the central config module under core."
    docs = [_mk_doc(a), _mk_doc(b), _mk_doc(c)]
    kept = _dedupe_chunks(docs)
    assert len(kept) == 3


def test_dedupe_keeps_short_chunks_unchanged():
    # Chunks shorter than the shingle size have at most one shingle and
    # shouldn't be dropped even if they happen to match.
    docs = [_mk_doc("Important note.", 0), _mk_doc("Important note.", 1)]
    kept = _dedupe_chunks(docs)
    assert len(kept) == 2


def test_dedupe_keeps_paraphrased_chunks_with_low_overlap():
    # Two paragraphs that share some vocabulary but aren't near-duplicates.
    # Shingle overlap should be well below 60% and both should survive.
    a = (
        "The replication subsystem handles failover between primary and "
        "secondary nodes automatically when heartbeat signals are missed."
    )
    b = (
        "Failover is configurable per-region and respects explicit "
        "maintenance windows set by operators during planned outages."
    )
    docs = [_mk_doc(a), _mk_doc(b)]
    kept = _dedupe_chunks(docs)
    assert len(kept) == 2

'''
def test_chunker_drops_near_duplicates_across_paragraphs_in_one_file(tmp_path):
    # End-to-end: a README with the same paragraph twice should yield
    # fewer chunks than a README with two distinct paragraphs.
    para = (
        "Project Foo is a small library that helps with text processing. "
        "It supports tokenization, stemming, and lemmatization out of the box. "
        "It's used by several internal tools and has a stable public API."
    )
    (tmp_path / "README.md").write_text(
        "## Section A\n\n" + para + "\n\n## Section B\n\n" + para + "\n"
    )
    repo_dup = tmp_path / "repo_dup"
    repo_dup.mkdir()
    (repo_dup / "README.md").write_text(
        "## Section A\n\n" + para + "\n\n## Section B\n\n" + para + "\n"
    )

    repo_distinct = tmp_path / "repo_distinct"
    repo_distinct.mkdir()
    (repo_distinct / "README.md").write_text(
        "## Section A\n\n"
        + para
        + "\n\n## Section B\n\n"
        + "Project Bar is a different library focused on parsing CSV files efficiently."
        + "\n"
    )

    docs_dup = load_and_chunk(repo_dup)
    docs_distinct = load_and_chunk(repo_distinct)

    assert len(docs_dup) < len(docs_distinct), (
        f"expected dedup to reduce chunk count: dup={len(docs_dup)} "
        f"distinct={len(docs_distinct)}"
    )
'''