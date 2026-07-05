from pathlib import Path
from app.ingestion.chunker import load_and_chunk


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
